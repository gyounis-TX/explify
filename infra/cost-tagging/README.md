# AWS cost attribution & tagging

This directory makes the monthly AWS bill answerable **per application**. Today the
account (`628475584741`, `us-east-1`) has **no cost-allocation tags**, so the bill
can only be read by *service* (ECS, ALB, Bedrock…), not by *app*.

## TL;DR — what was the May 2026 bill?

| Half | Amount | What it is |
|---|---|---|
| Amazon Web Services, Inc. | **$232.69** | Infra: Fargate, ALBs, NAT, VPC, RDS |
| Anthropic, PBC (Marketplace) | **$258.31** | Claude model calls via Bedrock |
| **Grand total** | **$491.00** | |

Top services: Claude **Sonnet 4.6 $197.91**, ECS Fargate $73.67, Load Balancers
$50.33, VPC/IPv4 $41.04, Claude **Haiku 4.5 $36.56**, NAT Gateway $33.48,
Claude Sonnet 4 $7.59, RDS $14.33.

The apps that run on AWS are **explify, Pulscribe, YCAPortal** (each an ECS/Fargate
service behind its own ALB) and **CathCPT** (Lambda). Bedrock is used by explify,
Pulscribe, CathCPT and (negligibly) Systolic. YCAPortal uses no Bedrock.

## Two scripts (run once, with an admin/tagging-capable AWS profile)

1. `./tag-resources.sh` — tags this app's ECS cluster/service, ALB, target groups
   (and optionally RDS/S3/CloudFront) with `app=explify`, and enables tag
   propagation so future Fargate tasks inherit the tag. Idempotent; adds-only.
2. `./setup-bedrock-inference-profiles.sh` — creates tagged **application inference
   profiles** for the Claude models explify uses, and prints a JSON map.

Then **activate the tag**: Billing Console → Cost Allocation Tags → User-defined →
select `app` → Activate (≈24 h to populate; counts usage from activation onward).

### Turning on Bedrock attribution (opt-in, zero-risk until enabled)

`sidecar/llm/client.py` reads an optional env var `BEDROCK_APP_PROFILE_MAP` — a JSON
object mapping a system inference-profile ID to the tagged application-profile ARN.
When **unset, behavior is identical to today** (verified). To enable:

```bash
# value comes from setup-bedrock-inference-profiles.sh
export BEDROCK_APP_PROFILE_MAP='{"us.anthropic.claude-sonnet-4-6":"arn:aws:bedrock:us-east-1:628475584741:application-inference-profile/explify-...", ...}'
```

Set it on the `explify-api` ECS task definition (env var) and redeploy.

---

## Usage analysis (why this matters) — the apps are nearly idle at the HTTP layer

From Cost Explorer (May 2026), grouping the ELB charge by usage type:

- **LoadBalancerUsage:** 2,232 LB-hours = exactly **3 ALBs** running 24×7 (744 h each).
- **LCUUsage:** only **13.2 LCU-hours for the entire month, across all 3 ALBs** —
  ≈ **$0.11**. An LCU covers 25 new conns/s, 3,000 active conns, 1 GB/h, 1,000
  rule-evals/s. 13.2 LCU-h over 744 h ≈ **0.018 LCU sustained** → essentially **no
  traffic**. explify and YCAPortal are very lightly used at the request layer.
- **Fargate:** 1,492 vCPU-hours / 744 h ≈ **2.0 vCPU running continuously** across the
  services — fixed minimum-size always-on tasks, not load-driven.
- **NAT Gateway:** 744 h = **one** NAT, **$33.48**, billed flat regardless of traffic.
- **RDS:** a single `db.t4g.micro`, 744 h, $14.33.

**Conclusion:** the AWS-direct $232 is dominated by *fixed/idle* infrastructure, not
usage. ~**$125/mo** (ALBs $50 + NAT $33 + VPC/IPv4 $41) is "lights-on" networking.

## Consolidation opportunity: 3 ALBs → 1 shared ALB

| Item | Today | After consolidation | Saving |
|---|---|---|---|
| ALBs | 3 × ~$16.4/mo base ≈ **$50** | 1 shared ALB ≈ **$16.7** | **~$33/mo** |
| NAT Gateway | 1 × **$33.48** | VPC endpoints (S3 free; ECR/Bedrock ~$7 ea) or public-subnet tasks | **~$20–30/mo** |
| VPC / public IPv4 | **$41** (~11 IPs @ $3.6/mo) | fewer ALB/NAT IPs | **~$10–20/mo** |

**Potential infra savings ≈ $60–90/mo (~25–40% of the AWS-direct bill)** with no
impact on these near-idle workloads.

**How:** one ALB with host-based listener rules —
`api.explify.app` → explify TG, `<pulscribe host>` → pulscribe TG,
`<yca host>` → yca-portal TG — sharing one set of listeners/cert (ACM supports
multiple SANs / SNI). Put the Fargate services in the shared ALB's target groups.

**Trade-offs:** one ALB becomes a shared failure/config domain for all three apps;
listener-rule and security-group changes are now cross-app. Given (a) same owner,
(b) near-zero traffic, the coupling risk is low and the saving is real — **recommended**.

**Bigger swing (optional):** because traffic is so low, scale-to-zero compute
(AWS App Runner, or Lambda + API Gateway for the lighter apps) would remove the
always-on Fargate *and* the ALB base cost entirely. Larger re-architecture; revisit
if you want to drive the AWS-direct half toward ~$0 at idle.

> Numbers are from AWS Cost Explorer for the May 1–31 2026 billing period
> (account 628475584741). Re-run after tagging to get the exact per-app split.
