# Async extraction — deploy & rollout (scaffolding)

Splits explify's heavy OCR/extraction off the request path into a **scale-to-zero
Fargate worker** fed by **SQS**, so the always-on API stops paying for peak OCR
capacity. Full rationale in [`docs/async-extraction/DESIGN.md`](../../docs/async-extraction/DESIGN.md).

> **Status: scaffolding.** All app code is additive and behind `ASYNC_EXTRACTION`
> (off by default). The synchronous `/extract/*` path is untouched. Syntax-checked but
> not yet integration-tested against live AWS/RDS.

## Pieces

| Where | What |
|---|---|
| `sidecar/jobs/` | job model, Postgres store (`CREATE TABLE IF NOT EXISTS`), SQS wrapper, S3 I/O |
| `sidecar/worker/extraction_worker.py` | SQS consumer that runs the **existing** `ExtractionPipeline` |
| `sidecar/api/jobs_routes.py` | additive `POST /extract/jobs` + `GET /extract/jobs/{id}` |
| `infra/async-extraction/worker.Dockerfile` | worker image (same deps as the sidecar) |
| `infra/async-extraction/template.yaml` | SQS + DLQ + worker service (desiredCount 0) + queue-depth autoscaling + IAM |

## Deploy

1. **Build & push the worker image**
   ```bash
   docker build -f infra/async-extraction/worker.Dockerfile -t <ecr>/explify-worker:latest ./sidecar
   docker push <ecr>/explify-worker:latest
   ```
2. **Deploy the stack** (alongside the existing service — nothing is modified):
   ```bash
   aws cloudformation deploy \
     --template-file infra/async-extraction/template.yaml \
     --stack-name explify-async-extraction \
     --capabilities CAPABILITY_IAM \
     --parameter-overrides \
       WorkerImageUri=<ecr>/explify-worker:latest \
       Subnets=subnet-aaa,subnet-bbb \
       SecurityGroups=sg-xxxx \
       DatabaseSecretArn=arn:aws:secretsmanager:...:secret:explify-DATABASE_URL
   ```
   The stack creates a dedicated **private, encrypted** PHI bucket
   (`explify-extraction-jobs-<account>`) with a lifecycle rule that expires objects
   after `JobRetentionDays` (default 3). Note the `QueueUrl` and `JobsBucketName` outputs.
3. **Wire the API** (one line) in `sidecar/main.py` (or `api/routes.py`), guarded by the flag:
   ```python
   from api.jobs_routes import router as jobs_router
   from jobs.models import async_extraction_enabled
   if async_extraction_enabled():
       app.include_router(jobs_router)
   ```
4. Set on the **API** task: `ASYNC_EXTRACTION=true`, `EXTRACTION_QUEUE_URL=<QueueUrl output>`,
   `EXTRACTION_S3_BUCKET=<JobsBucketName output>` (+ existing DB env). The API task role
   needs `sqs:SendMessage` on the queue, `s3:PutObject` on
   `<JobsBucket>/extraction-jobs/input/*`, and `s3:GetObject` on
   `<JobsBucket>/extraction-jobs/result/*` (to return results on poll).
5. Build/serve the **web frontend** with `VITE_ASYNC_EXTRACTION=true` so the client uses
   submit+poll. (Both flags must be on: backend `ASYNC_EXTRACTION` and frontend
   `VITE_ASYNC_EXTRACTION`. With only the backend flag, the API exposes the job
   endpoints but the SPA keeps calling the sync routes — a safe intermediate state.)

## Verify

```bash
# submit
curl -F file=@sample.pdf https://api.explify.app/extract/jobs        # -> 202 {"job_id": "..."}
# poll
curl https://api.explify.app/extract/jobs/<job_id>                   # status -> done, result JSON
```
Watch the worker scale `0 → 1` within ~a minute of submission (CloudWatch alarm), process
the job, and scale back to `0` after the queue drains.

## PHI / retention

- Job input/result objects live in a **dedicated private bucket**
  (`explify-extraction-jobs-<account>`) created by the stack — public access blocked,
  SSE on, **not** the public frontend/CDN bucket. Objects auto-expire after
  `JobRetentionDays` (default 3) via the bucket lifecycle rule.
- SQS carries **only the `job_id`** — no PHI.
- The `extraction_jobs` table is part of the canonical migration
  (`storage/migrations/schema.sql`) and its rows are purged after 7 days by
  `enforce_data_retention()`. `jobs/store.py` keeps a matching
  `CREATE TABLE IF NOT EXISTS` as a worker-startup fallback.

## Known follow-ups before production

- ~~Vision-OCR in the worker~~ **Done.** The worker builds the same per-user client as
  the sync routes via `llm.factory.build_extract_llm_client(job.user_id)`, so
  low-confidence pages get the Bedrock vision-OCR fallback (accuracy parity). The worker
  task role already has `bedrock:InvokeModel`.
- ~~Frontend submit+poll~~ **Done.** `sidecarApi.extractPdf/extractFile` transparently
  submit a job and poll `GET /extract/jobs/{id}` when `VITE_ASYNC_EXTRACTION=true`
  (web only — `IS_TAURI` desktop always uses the sync sidecar). Same `ExtractionResult`
  return type, so `ImportScreen` and other callers are unchanged. Build the web app
  with `VITE_ASYNC_EXTRACTION=true` to turn it on.
- ~~DB migration + S3 lifecycle~~ **Done.** `extraction_jobs` is in
  `storage/migrations/schema.sql` (purged after 7 days by `enforce_data_retention()`);
  job objects live in a dedicated private bucket with a lifecycle expiry built into the
  stack.
- **Scale-from-zero nuance:** the CloudWatch alarm drives `0 → N` via a step policy
  (target-tracking can't initiate from 0). Tune thresholds/cooldowns to your latency
  tolerance.

## Roll back

`aws cloudformation delete-stack --stack-name explify-async-extraction` and set
`ASYNC_EXTRACTION=false`. The synchronous extraction path is unaffected throughout.
