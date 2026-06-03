# Async extraction pipeline — design

**Status:** proposal + scaffolding (this PR). Nothing here is wired into the running
app yet; all new code is additive and behind the `ASYNC_EXTRACTION` flag.

## Problem

explify's cost is dominated by an **always-on Fargate sidecar** that sits near-idle
most of the time (measured: all app ALBs served ~13 LCU-hours in May 2026), yet it
must stay provisioned 24×7 because the expensive work runs **synchronously inside the
request**:

```
POST /extract/pdf  ──▶  ExtractionPipeline.extract_from_pdf()
                         ├─ tesseract OCR (CPU-bound, seconds–minutes)
                         ├─ Bedrock vision-OCR for low-confidence pages
                         └─ table parsing / structured extraction
                        ◀── ExtractionResult (in the HTTP response)
```

Because a single upload can pin a worker for a long time and burst concurrency is
unpredictable, the service is sized and kept warm for peak — so you pay for capacity
that's idle the rest of the time. This is also exactly why explify is a **poor fit for
Lambda** (heavy image → slow cold start; `asyncpg` → in-VPC + connection-limit issues;
per-cold-start `run_migrations()`).

## Goal

Decouple the heavy OCR/extraction work from the request path so that:

1. The **API surface becomes thin and bursty-cheap** (no CPU-pinning requests) — small
   enough to later run on App Runner or even Lambda.
2. The **heavy worker scales to zero** when no jobs are queued, and scales out only
   while work exists — you pay for extraction compute *only while extracting*.
3. Long jobs no longer risk client/ALB timeouts; retries and failures are first-class.

## Proposed architecture

```
                      ┌───────────────────────────┐
  client  ──upload──▶ │  API (thin, FastAPI)      │
                      │  POST /extract/jobs        │
                      │   1. put input → S3        │
                      │   2. INSERT job (queued)   │
                      │   3. SQS send {job_id}     │──┐
                      │   ◀── 202 {job_id}         │  │
                      │  GET /extract/jobs/{id}    │  │  SQS (standard) + DLQ
                      └───────────────────────────┘  │
                                ▲                     ▼
                        poll    │            ┌──────────────────────────┐
                        status  │            │ Worker (Fargate, min 0)  │
                                └────────────│  long-poll SQS           │
                                  job row    │  ├─ download input (S3)  │
                                  + result   │  ├─ ExtractionPipeline   │  ◀─ reuses the
                                             │  ├─ write result (S3+DB) │     EXISTING pipeline
                                             │  └─ delete msg / DLQ     │     unchanged
                                             └──────────────────────────┘
                                  autoscale on queue depth: 0 ⇄ N
```

### Why a Fargate worker (not Lambda) for the heavy half

The worker keeps the heavy image (tesseract/poppler/weasyprint/PyMuPDF), connects to
RDS normally (in-VPC, persistent pool), and has no 15-min cap. SQS-driven autoscaling
takes it **0 → N** while a backlog exists and back to **0** when drained, so it's
"serverless-like" on cost without Lambda's cold-start/RDS pain. Lambda is fine for the
*thin API*, later — not for the OCR worker.

## Job lifecycle & data model

`extraction_jobs` (Postgres):

| column | notes |
|---|---|
| `job_id` (uuid, pk) | idempotency key; also the SQS message body |
| `user_id`, `practice_id` | from `request.state` (AuthMiddleware) |
| `status` | `queued → processing → done \| failed` |
| `input_s3_key` | uploaded source document |
| `result_s3_key` | serialized `ExtractionResult` (large text kept off the row) |
| `kind` | `pdf \| image \| text` (which pipeline entry to call) |
| `attempts`, `last_error` | retry/diagnostics |
| `created_at`, `updated_at`, `completed_at` | timing + retention |

States are advisory; **SQS is the source of truth for "needs work."** The worker is
**idempotent**: it re-reads the job row, and if `status=done` it just deletes the
message (handles SQS at-least-once delivery).

## Reliability

- **Visibility timeout > max expected job duration** (e.g. 15 min) so a long OCR isn't
  redelivered mid-flight.
- **DLQ** after `maxReceiveCount` (e.g. 3) captures poison documents for inspection.
- **Retries** are automatic via SQS redelivery; `attempts` is recorded for visibility.
- **Backpressure**: queue absorbs bursts; worker count is bounded by `MaxCapacity`.

## Clinical-safety / PHI

- Input files land in S3 with **SSE** and a short **lifecycle expiry** (e.g. 24–72 h);
  results follow the existing `enforce_data_retention()` policy.
- The worker reuses the same PHI scrubbing already in `main.py` / Sentry `before_send`.
- No PHI in SQS messages — the body is **only the `job_id`**; everything else is in
  S3/DB behind IAM.

## Cost impact

- **Worker:** runs only while jobs exist → **scale-to-zero**; you pay extraction
  compute per-burst instead of 24×7.
- **API:** no longer CPU-pinned by extraction → can be downsized now, and becomes a
  candidate for App Runner / Lambda later (its remaining work is light JSON + Bedrock
  text calls).
- Net direction: explify's always-on Fargate baseline drops toward the cost of the
  thin API, with heavy compute converted to on-demand burst.

## Rollout (incremental, reversible)

1. **Ship scaffolding (this PR)** — additive, `ASYNC_EXTRACTION` off by default. No
   behavior change.
2. Deploy SQS + DLQ + worker service (`infra/async-extraction/`) with `MinCapacity=0`.
3. Mount the jobs router (one line, see infra README) and flip `ASYNC_EXTRACTION=true`
   in a staging task; exercise `POST /extract/jobs` + polling.
4. Migrate the frontend's upload flow from `POST /extract/pdf` to the job endpoints
   (submit → poll). Keep the sync route as a fallback during transition.
5. Once stable, **downsize the API service** (fewer/smaller tasks) and revisit
   App Runner/Lambda for the API.
6. Roll back at any step by setting `ASYNC_EXTRACTION=false` and/or
   `sam delete` of the async stack — the sync path is untouched throughout.

## Scope of the scaffolding in this PR

- `sidecar/jobs/` — job model, Postgres store (`CREATE TABLE IF NOT EXISTS`), SQS
  wrapper, S3 I/O.
- `sidecar/worker/extraction_worker.py` — the SQS consumer that calls the **existing**
  `ExtractionPipeline`, building the same per-user vision-OCR client as the sync routes
  (via `llm.factory.build_extract_llm_client`) for accuracy parity.
- `sidecar/llm/factory.py` — request-free `build_extract_llm_client(user_id)`, shared by
  the sync routes and the worker (the sync `_build_extract_llm_client(request)` now
  delegates to it — a pure refactor, no behavior change).
- `sidecar/api/jobs_routes.py` — additive `POST /extract/jobs` + `GET /extract/jobs/{id}`
  router (not mounted unless you wire it + flip the flag).
- `infra/async-extraction/` — SQS+DLQ+worker CloudFormation, worker Dockerfile, README.

These are **prototype scaffolding**: syntax-checked, not yet integration-tested against
live AWS/RDS. Treat as a reviewable starting point, not production-ready.
