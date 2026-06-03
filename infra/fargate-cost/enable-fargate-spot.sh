#!/usr/bin/env bash
#
# Move the explify API ECS service onto Fargate Spot (~70% cheaper compute) for the hours
# it runs. Spot tasks can be reclaimed with a 2-minute warning; ECS relaunches them, so
# expect a brief blip on interruption. Use ON_DEMAND_BASE=1 to keep one guaranteed
# on-demand task (more stable, but that task is billed at full price).
#
# Only the API service is affected. The async-extraction worker has its own capacity
# config; RDS is untouched.
#
# NOTE: switching an existing launch-type service to a capacity-provider strategy
# requires a forced new deployment (handled below).
#
# Rollback to 100% on-demand:
#   aws ecs update-service --cluster explify --service explify-api-service-cifg1mjg \
#     --capacity-provider-strategy capacityProvider=FARGATE,weight=1 --force-new-deployment

set -euo pipefail
CLUSTER="${CLUSTER:-explify}"
SERVICE="${SERVICE:-explify-api-service-cifg1mjg}"
REGION="${AWS_REGION:-us-east-1}"
ON_DEMAND_BASE="${ON_DEMAND_BASE:-0}"   # 0 = all Spot (max savings); 1 = one on-demand base

echo "==> Associating FARGATE + FARGATE_SPOT capacity providers with cluster '$CLUSTER'"
aws ecs put-cluster-capacity-providers \
  --cluster "$CLUSTER" --region "$REGION" \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1 >/dev/null

echo "==> Switching service '$SERVICE' to Spot (on-demand base=$ON_DEMAND_BASE)"
if [ "$ON_DEMAND_BASE" -gt 0 ]; then
  STRATEGY="capacityProvider=FARGATE,base=${ON_DEMAND_BASE},weight=0 capacityProvider=FARGATE_SPOT,weight=1"
else
  STRATEGY="capacityProvider=FARGATE_SPOT,weight=1"
fi

# shellcheck disable=SC2086
aws ecs update-service \
  --cluster "$CLUSTER" --service "$SERVICE" --region "$REGION" \
  --capacity-provider-strategy $STRATEGY \
  --force-new-deployment >/dev/null

echo "==> Done. Verify: aws ecs describe-services --cluster $CLUSTER --services $SERVICE \\"
echo "        --query 'services[0].capacityProviderStrategy'"
