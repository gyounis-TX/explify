#!/usr/bin/env bash
#
# Apply the `app=explify` cost-allocation tag to this app's AWS resources so that
# AWS Cost Explorer / the monthly bill can be split per application.
#
# Background: the explify backend runs as an ECS/Fargate service behind an
# Application Load Balancer in account 628475584741 (us-east-1). None of this
# infrastructure is currently tagged, which is why "which app costs what" cannot
# be answered from the bill today.
#
# This script is IDEMPOTENT and only ADDS a single tag (app=explify). It does not
# delete, resize, or restart anything (unless you pass --force-redeploy).
#
# Requirements: AWS CLI v2, credentials with tagging permissions
# (ecs:TagResource, ecs:UpdateService, elasticloadbalancing:AddTags,
#  rds:AddTagsToResource, ce:* not required). Run it ONCE.
#
# After running, activate the `app` tag as a cost-allocation tag:
#   Billing Console -> Cost Allocation Tags -> User-defined -> select "app" -> Activate
# (takes ~24h to appear in Cost Explorer; only affects usage from activation onward).

set -euo pipefail

APP="explify"
REGION="us-east-1"
CLUSTER="explify"
SERVICE="explify-api-service-cifg1mjg"

# Optional: set these if this app owns them (leave blank to skip).
RDS_INSTANCE_ID=""              # e.g. "explify-db"  -> tags the RDS instance
FRONTEND_BUCKET="explify-frontend"  # S3 bucket for the static frontend ("" to skip)
CLOUDFRONT_DIST_ID=""           # e.g. "E1ABCDEFGHIJ" ("" to skip)
FORCE_REDEPLOY="no"             # "yes" forces a new deployment so RUNNING tasks pick up the tag now

[ "${1:-}" = "--force-redeploy" ] && FORCE_REDEPLOY="yes"

TAG_KEY="app"
log() { printf '  %s\n' "$*"; }

echo "==> Tagging ECS cluster + service ($CLUSTER / $SERVICE) with $TAG_KEY=$APP"
CLUSTER_ARN=$(aws ecs describe-clusters --clusters "$CLUSTER" --region "$REGION" \
  --query 'clusters[0].clusterArn' --output text)
SERVICE_ARN=$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" --region "$REGION" \
  --query 'services[0].serviceArn' --output text)

aws ecs tag-resource --resource-arn "$CLUSTER_ARN" --tags "key=$TAG_KEY,value=$APP" --region "$REGION"
aws ecs tag-resource --resource-arn "$SERVICE_ARN" --tags "key=$TAG_KEY,value=$APP" --region "$REGION"
log "tagged cluster + service"

# Make FUTURE tasks inherit the service tag (this is what Fargate cost allocation reads).
# Takes effect on the next deployment; use --force-redeploy to apply immediately.
echo "==> Enabling tag propagation to tasks"
aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" --region "$REGION" \
  --propagate-tags SERVICE --enable-ecs-managed-tags \
  $([ "$FORCE_REDEPLOY" = "yes" ] && echo "--force-new-deployment") >/dev/null
log "propagate-tags=SERVICE enabled (force-redeploy=$FORCE_REDEPLOY)"

# Discover and tag the ALB + target groups attached to this service.
echo "==> Tagging Application Load Balancer + target groups"
TG_ARNS=$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" --region "$REGION" \
  --query 'services[0].loadBalancers[].targetGroupArn' --output text)
if [ -n "$TG_ARNS" ] && [ "$TG_ARNS" != "None" ]; then
  for TG in $TG_ARNS; do
    aws elbv2 add-tags --resource-arns "$TG" --tags "Key=$TAG_KEY,Value=$APP" --region "$REGION"
    log "tagged target group $(basename "$TG")"
    ALB_ARNS=$(aws elbv2 describe-target-groups --target-group-arns "$TG" --region "$REGION" \
      --query 'TargetGroups[0].LoadBalancerArns[]' --output text)
    for ALB in $ALB_ARNS; do
      aws elbv2 add-tags --resource-arns "$ALB" --tags "Key=$TAG_KEY,Value=$APP" --region "$REGION"
      log "tagged load balancer $(echo "$ALB" | sed 's#.*loadbalancer/##')"
    done
  done
else
  log "no target groups found on service (skipping ALB)"
fi

# Optional: RDS instance
if [ -n "$RDS_INSTANCE_ID" ]; then
  echo "==> Tagging RDS instance $RDS_INSTANCE_ID"
  RDS_ARN=$(aws rds describe-db-instances --db-instance-identifier "$RDS_INSTANCE_ID" --region "$REGION" \
    --query 'DBInstances[0].DBInstanceArn' --output text)
  aws rds add-tags-to-resource --resource-name "$RDS_ARN" --tags "Key=$TAG_KEY,Value=$APP" --region "$REGION"
  log "tagged RDS $RDS_INSTANCE_ID"
fi

# Optional: S3 frontend bucket (merge-safe: preserves existing tags)
if [ -n "$FRONTEND_BUCKET" ]; then
  echo "==> Tagging S3 bucket $FRONTEND_BUCKET (merge)"
  EXISTING=$(aws s3api get-bucket-tagging --bucket "$FRONTEND_BUCKET" --region "$REGION" \
    --query 'TagSet' --output json 2>/dev/null || echo '[]')
  MERGED=$(printf '%s' "$EXISTING" | python3 -c "import json,sys; t=[x for x in json.load(sys.stdin) if x['Key']!='$TAG_KEY']; t.append({'Key':'$TAG_KEY','Value':'$APP'}); print(json.dumps({'TagSet':t}))")
  aws s3api put-bucket-tagging --bucket "$FRONTEND_BUCKET" --tagging "$MERGED" --region "$REGION"
  log "tagged bucket $FRONTEND_BUCKET"
fi

# Optional: CloudFront distribution
if [ -n "$CLOUDFRONT_DIST_ID" ]; then
  echo "==> Tagging CloudFront $CLOUDFRONT_DIST_ID"
  CF_ARN="arn:aws:cloudfront::$(aws sts get-caller-identity --query Account --output text):distribution/$CLOUDFRONT_DIST_ID"
  aws cloudfront tag-resource --resource "$CF_ARN" --tags "Items=[{Key=$TAG_KEY,Value=$APP}]" --region us-east-1
  log "tagged CloudFront $CLOUDFRONT_DIST_ID"
fi

echo "==> Done. Remember to activate the 'app' cost-allocation tag in the Billing console."
