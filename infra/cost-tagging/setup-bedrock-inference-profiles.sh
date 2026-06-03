#!/usr/bin/env bash
#
# Create per-app Bedrock APPLICATION inference profiles so that Claude/Bedrock
# spend can be attributed to explify in Cost Explorer.
#
# Why this is needed: ~half of the monthly AWS bill is Claude model usage, billed
# through the "Anthropic, PBC" Marketplace line. Raw Bedrock model invocations are
# NOT taggable per-app. The supported mechanism is an *application inference
# profile* (a tagged wrapper around a system inference profile). You invoke the
# model through the profile's ARN, and the profile's `app` tag flows into the bill.
#
# This script creates one application inference profile per model explify uses,
# tags it app=explify, and prints a JSON map you paste into the
# BEDROCK_APP_PROFILE_MAP env var (read by sidecar/llm/client.py). Until that env
# var is set, nothing changes — calls keep using the plain system profiles.
#
# Requirements: AWS CLI v2 with bedrock:CreateInferenceProfile, bedrock:ListInferenceProfiles.

set -euo pipefail
APP="explify"
REGION="us-east-1"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

# System inference-profile IDs explify invokes today (from sidecar/llm/client.py _BEDROCK_MODEL_MAP).
SYSTEM_PROFILE_IDS=(
  "us.anthropic.claude-sonnet-4-6"
  "us.anthropic.claude-haiku-4-5-20251001-v1:0"
  "us.anthropic.claude-opus-4-6-20250620-v1:0"
  "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)

echo "{"
first=1
for SID in "${SYSTEM_PROFILE_IDS[@]}"; do
  SRC_ARN="arn:aws:bedrock:${REGION}:${ACCOUNT}:inference-profile/${SID}"
  NAME="${APP}-$(echo "$SID" | tr '.:' '--')"
  # Create (idempotent-ish: ignore "already exists")
  OUT=$(aws bedrock create-inference-profile \
        --inference-profile-name "$NAME" \
        --model-source "copyFrom=${SRC_ARN}" \
        --tags "key=app,value=${APP}" \
        --region "$REGION" 2>/dev/null || true)
  ARN=$(printf '%s' "$OUT" | python3 -c "import json,sys;d=sys.stdin.read();print(json.loads(d).get('inferenceProfileArn','') if d.strip() else '')" 2>/dev/null || true)
  if [ -z "$ARN" ]; then
    ARN=$(aws bedrock list-inference-profiles --type-equals APPLICATION --region "$REGION" \
          --query "inferenceProfileSummaries[?inferenceProfileName=='${NAME}'].inferenceProfileArn | [0]" \
          --output text 2>/dev/null || true)
  fi
  [ "$first" = 1 ] || echo ","
  printf '  "%s": "%s"' "$SID" "$ARN"
  first=0
done
echo ""
echo "}"
echo
echo "# ^ Paste the object above (single line) into BEDROCK_APP_PROFILE_MAP for the explify ECS task." >&2
