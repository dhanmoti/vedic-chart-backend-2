#!/usr/bin/env bash
set -euo pipefail

: "${SERVICE_NAME:=vedic-chart-backend}"
: "${REGION:=us-central1}"
: "${IMAGE:=gcr.io/PROJECT_ID/vedic-chart-backend:latest}"

# Locked baseline profile from docs/cloud-run-tuning.md.
: "${CONCURRENCY:=2}"
: "${CPU:=1}"
: "${MEMORY:=1Gi}"
: "${MIN_INSTANCES:=0}"
: "${MAX_INSTANCES:=20}"

# Cache backend values should be set by deploy environment.
: "${CACHE_BACKEND:=redis}"
: "${REDIS_URL:=redis://YOUR_MEMORSTORE_HOST:6379}"

gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --concurrency "${CONCURRENCY}" \
  --cpu "${CPU}" \
  --memory "${MEMORY}" \
  --min-instances "${MIN_INSTANCES}" \
  --max-instances "${MAX_INSTANCES}" \
  --set-env-vars "CACHE_BACKEND=${CACHE_BACKEND},REDIS_URL=${REDIS_URL}" \
  --allow-unauthenticated
