#!/usr/bin/env bash
# deploy.sh: full one-shot deployment for publication-reports
# Usage: edit the variables below, then: bash deploy.sh
#
# NOTE: gcloud_app.yaml is the authoritative config (see ../GCLOUD_POLICY.md and
#       ../manage.py). This script is the standalone fallback, keep it in sync.
#
# First-time flow:
#   1. Set PROJECT, REGION, and email vars, leave WEEKLY_JOB_TOKEN empty.
#   2. Run: bash deploy.sh, this builds and deploys the service.
#   3. Copy the printed SERVICE_URL into env.yaml as BASE_URL.
#   4. Set WEEKLY_JOB_TOKEN to the value from env.yaml.
#   5. Run: bash deploy.sh, redeploys with BASE_URL and creates the scheduler.

set -euo pipefail

PROJECT=your-gcp-project
REGION=europe-west1
SERVICE_NAME=pubrep
BUCKET="${PROJECT}-pubrep-data"
SA="pubrep-sa@${PROJECT}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/pubrep/app:latest"

# Paste your WEEKLY_JOB_TOKEN from env.yaml here before the second run
WEEKLY_JOB_TOKEN=""

# ── enable APIs ───────────────────────────────────────────────────────────────
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project="${PROJECT}"

# ── Artifact Registry repo ────────────────────────────────────────────────────
gcloud artifacts repositories create pubrep \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT}" 2>/dev/null || true

# ── data bucket ───────────────────────────────────────────────────────────────
gcloud storage buckets create "gs://${BUCKET}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --project="${PROJECT}" 2>/dev/null || echo "bucket ${BUCKET} already exists"
# `buckets create` has no --labels flag; labels are set via update.
gcloud storage buckets update "gs://${BUCKET}" \
  --update-labels=app=pub-reports --project="${PROJECT}"

# ── service account for Cloud Scheduler ──────────────────────────────────────
gcloud iam service-accounts create pubrep-sa \
  --display-name="Pub Reports, Cloud Scheduler invoker" \
  --project="${PROJECT}" 2>/dev/null || true

gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${SA}" \
  --role=roles/run.invoker --condition=None

# The service RUNS AS this SA (see --service-account below), so it needs
# read/write access to the GCS bucket mounted at /mnt/data.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA}" --role=roles/storage.objectAdmin

# ── build container image ─────────────────────────────────────────────────────
gcloud builds submit --tag "${IMAGE}" --project="${PROJECT}" .

# ── deploy Cloud Run service ──────────────────────────────────────────────────
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --service-account="${SA}" \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --max-instances=1 \
  --concurrency=1 \
  --timeout=600 \
  --add-volume="name=data,type=cloud-storage,bucket=${BUCKET}" \
  --add-volume-mount="volume=data,mount-path=/mnt/data" \
  --env-vars-file=env.yaml \
  --labels=app=pub-reports \
  --project="${PROJECT}"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --format='value(status.url)' \
  --project="${PROJECT}")

# ── Cloud Scheduler trigger ───────────────────────────────────────────────────
if [ -n "${WEEKLY_JOB_TOKEN}" ]; then
  gcloud scheduler jobs create http pubrep-weekly-sched \
    --location="${REGION}" \
    --schedule="0 8 * * 1" \
    --uri="${SERVICE_URL}/internal/run-weekly?token=${WEEKLY_JOB_TOKEN}" \
    --http-method=POST \
    --time-zone="Europe/Berlin" \
    --attempt-deadline=600s \
    --project="${PROJECT}" 2>/dev/null || \
  gcloud scheduler jobs update http pubrep-weekly-sched \
    --location="${REGION}" \
    --schedule="0 8 * * 1" \
    --uri="${SERVICE_URL}/internal/run-weekly?token=${WEEKLY_JOB_TOKEN}" \
    --http-method=POST \
    --time-zone="Europe/Berlin" \
    --attempt-deadline=600s \
    --project="${PROJECT}"
  echo "Scheduler job pubrep-weekly-sched created/updated."
else
  echo "WEEKLY_JOB_TOKEN not set, skipping scheduler setup."
  echo "Set it at the top of this script and re-run to create the scheduler job."
fi

echo ""
echo "Deployment complete."
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Next steps (first deploy only):"
echo "  1. Paste '${SERVICE_URL}' as BASE_URL in env.yaml"
echo "  2. Set WEEKLY_JOB_TOKEN at the top of this script"
echo "  3. Run this script again"
echo ""
echo "To trigger manually: gcloud scheduler jobs run pubrep-weekly-sched --location=${REGION}"
echo "To view logs:        gcloud run services logs tail ${SERVICE_NAME} --region=${REGION}"
