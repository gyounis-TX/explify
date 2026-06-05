# AWS cost rollout runbook

One-page plan to roll out the cost work across the four PRs, in dependency order, with
expected $ impact and rollback. Account `628475584741`, us-east-1.

## Baseline (May 2026, from Cost Explorer)

**$491.00 total** = **$232.69 AWS infra** + **$258.31 Claude/Bedrock** (Anthropic, PBC — the "Marketplace" line).

Top lines: Sonnet 4.6 **$197.91** · Fargate **$73.67** · ALB **$50.33** (3 LBs) · VPC/IPv4 **$41.04** · Haiku 4.5 **$36.56** · NAT **$33.48** · Tax $30.43 · RDS $14.33.

Apps on AWS: **Pulscribe** (ECS), **explify** (ECS + RDS + async worker), **YCAPortal** (ECS → Lambda), **CathCPT** (Lambda). **Systolic = Firebase**, ~$0.24 Bedrock only — nothing to do.

## The PRs

| Repo | PR | Contents |
|---|---|---|
| explify | #1 | tagging · Bedrock hook · async extraction · Fargate scheduling/Spot |
| Pulscribe | #3 | tagging · Bedrock recipe · Fargate scheduling/Spot |
| YCAPortal | #1 | tagging · scale-to-zero Lambda prototype |
| CathCPT | #1 | tagging · Bedrock recipe |

---

## Phase 0 — Visibility first (zero risk, do before anything else)

Tagging + Bedrock attribution change **no behavior** but let you *measure* per-app and verify
the estimates below with real numbers.

1. Run `infra/cost-tagging/tag-resources.sh` in each repo.
2. Run `infra/cost-tagging/setup-bedrock-inference-profiles.sh` (Pulscribe, explify, CathCPT); set `BEDROCK_APP_PROFILE_MAP` on each service.
3. **Billing → Cost Allocation Tags → activate `app`.**
4. Wait ~24–48 h, then read Cost Explorer grouped by `TAG:app`. **This replaces every estimate below with actuals.**

Saving: $0. Prerequisite for trusting the rest.

## Phase 1 — Low-risk compute wins

5. **YCAPortal → Lambda** (already running in a separate thread). Removes its **ALB (~$17/mo)** + its always-on Fargate slice (~$20/mo) → ~$0 idle. Decommission the old ALB/service once validated.
6. **Fargate scheduled scaling** — Pulscribe + explify: `aws cloudformation deploy … scheduled-scaling.yaml`. Scales to 0 nights/weekends. **~70% off their Fargate hours (~$30–35/mo).** Reversible via `delete-stack`.

## Phase 2 — Opt-in, slightly higher risk

7. **Fargate Spot** — Pulscribe + explify: `enable-fargate-spot.sh` (start all-Spot; `ON_DEMAND_BASE=1` if interruptions bite). **~$8–12/mo more.** Rollback = one `update-service`.
8. **explify async extraction** — deploy `infra/async-extraction/` (SQS + scale-to-zero worker + private PHI bucket), set backend `ASYNC_EXTRACTION=true`, then frontend `VITE_ASYNC_EXTRACTION=true`. Then **downsize the explify API** task (heavy OCR no longer on the request path). Roll back via flags / `delete-stack`.

## Phase 3 — Revisit after the above settles

9. **NAT Gateway ($33) / VPC endpoints** — measure first; interface endpoints can cost more than one NAT if you need many.
10. **Shared ALB** — only worthwhile if 2+ always-on ALBs remain after Phase 1–2 (~$17/mo, adds coupling). Deferred.
11. **Bedrock model right-sizing — the biggest remaining lever.** Sonnet 4.6 alone is **$198/mo**. Moving suitable Pulscribe/explify calls from Sonnet → Haiku (a fraction of the per-token price) can dwarf all the infra savings combined. Out of scope of these PRs; tackle as a focused, accuracy-gated change.

---

## Expected impact (estimate — confirm with Phase 0 actuals)

| Lever | ~Monthly saving |
|---|---|
| YCAPortal → Lambda (ALB + Fargate) | ~$35–45 |
| Scheduled scaling (Pulscribe + explify) | ~$30–35 |
| Fargate Spot (Pulscribe + explify) | ~$8–12 |
| **Infra subtotal (the $232 half)** | **~$80–95/mo → AWS-direct ≈ $130–150** |
| Bedrock right-sizing (Phase 3, separate) | potentially **$50–120** of the $258 half |

**Infra alone: ~$491 → ~$400–410/mo. With Bedrock right-sizing: meaningfully lower.**

## Cross-cutting safety

- Everything is **off by default / additive / reversible**; the synchronous paths and running
  services are unchanged until you opt in.
- Validated for syntax/templates only — **none executed against live AWS/RDS**, and frontend
  TS wasn't typechecked here. Before each apply: review, run the relevant tests
  (`npx tsc --noEmit`, `vitest`, sidecar tests), and do it in a low-traffic window — these
  touch live clinical services.
- Schedules default to **America/Chicago**, clinic hours 6am–8pm weekdays; widen if anyone
  works evenings/weekends.
