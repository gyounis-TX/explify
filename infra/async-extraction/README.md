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
       DatabaseSecretArn=arn:aws:secretsmanager:...:secret:explify-DATABASE_URL \
       S3Bucket=explify-frontend
   ```
   Note the `QueueUrl` output.
3. **Wire the API** (one line) in `sidecar/main.py` (or `api/routes.py`), guarded by the flag:
   ```python
   from api.jobs_routes import router as jobs_router
   from jobs.models import async_extraction_enabled
   if async_extraction_enabled():
       app.include_router(jobs_router)
   ```
4. Set on the **API** task: `ASYNC_EXTRACTION=true`, `EXTRACTION_QUEUE_URL=<QueueUrl output>`,
   and ensure `S3_BUCKET` + DB env are present. The API task role needs
   `sqs:SendMessage` on the queue and `s3:PutObject` on `extraction-jobs/input/*`.
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

- Job input/result objects live under `s3://<bucket>/extraction-jobs/`. **Add a
  lifecycle rule** expiring that prefix (e.g. 24–72 h). Objects are written with SSE.
- SQS carries **only the `job_id`** — no PHI.
- Promote the `CREATE TABLE IF NOT EXISTS` DDL in `jobs/store.py` into a real migration
  (the table is also covered by the existing `enforce_data_retention()` once wired).

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
- **Scale-from-zero nuance:** the CloudWatch alarm drives `0 → N` via a step policy
  (target-tracking can't initiate from 0). Tune thresholds/cooldowns to your latency
  tolerance.

## Roll back

`aws cloudformation delete-stack --stack-name explify-async-extraction` and set
`ASYNC_EXTRACTION=false`. The synchronous extraction path is unaffected throughout.
