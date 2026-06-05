# Fargate cost reduction — explify API

The explify API (`explify-api-service-cifg1mjg`) Fargate task runs **24×7** but is
near-idle most of the time. Two independent, reversible levers cut that without changing
the app. (The heavy OCR/extraction work is being moved to the scale-to-zero worker in
`infra/async-extraction/`; this targets the always-on API itself.)

| Lever | What it does | Rough saving | Risk |
|---|---|---|---|
| **Scheduled scaling** (`scheduled-scaling.yaml`) | Scale to **0 outside clinic hours**, back to 1 on weekday mornings | ~**70%** of Fargate hours | Off-hours requests wait for scale-up |
| **Fargate Spot** (`enable-fargate-spot.sh`) | Run on Spot capacity while up | ~**70%** of the remaining compute | Spot reclaim (2-min warning) → brief blip |

## Scheduled scaling

```bash
aws cloudformation deploy \
  --template-file infra/fargate-cost/scheduled-scaling.yaml \
  --stack-name explify-scheduled-scaling \
  --capabilities CAPABILITY_NAMED_IAM
```
Defaults: up **6am Mon–Fri**, down **8pm daily**, **America/Chicago**, daytime min 1 /
max 2. Tune via `--parameter-overrides`. Attaches to the **existing** service only; the
task definition and RDS are untouched. Roll back with `delete-stack`.

## Fargate Spot

```bash
./infra/fargate-cost/enable-fargate-spot.sh            # all Spot (max savings)
ON_DEMAND_BASE=1 ./infra/fargate-cost/enable-fargate-spot.sh   # keep 1 on-demand task (more stable)
```
Start with all-Spot given near-idle usage; switch to `ON_DEMAND_BASE=1` if you ever see a
disruptive interruption. Rollback command is in the script header.

## Verify

```bash
aws ecs describe-services --cluster explify --services explify-api-service-cifg1mjg \
  --query 'services[0].{desired:desiredCount,running:runningCount,cps:capacityProviderStrategy}'
```

## Notes
- Touches the **running production API service**. Scheduled scaling is additive/reversible;
  the Spot switch forces one new deployment.
- Validated for template/shell syntax; **not executed against live AWS** — review first.
- If you later move the API to App Runner/Lambda, retire these and the ALB with it.
- Don't run alongside a separate request-based autoscaling policy on the same service
  without reconciling which one owns desiredCount.
