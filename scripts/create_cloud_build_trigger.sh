#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
TRIGGER_NAME="${TRIGGER_NAME:-deploy-pharmaops-agent-main}"
REPO_OWNER="${REPO_OWNER:-Himanshuwagh}"
REPO_NAME="${REPO_NAME:-google-hackathon}"
BRANCH_PATTERN="${BRANCH_PATTERN:-^main$}"
BUILD_CONFIG="${BUILD_CONFIG:-cloudbuild.yaml}"
INCLUDE_LOGS="${INCLUDE_LOGS:-true}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is not set and no gcloud project is configured." >&2
  echo "Run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")"
CONNECT_URL="https://console.cloud.google.com/cloud-build/triggers;region=${REGION}/connect?project=${PROJECT_NUMBER}"

args=(
  builds triggers create github
  "--project=${PROJECT_ID}"
  "--region=${REGION}"
  "--name=${TRIGGER_NAME}"
  "--repo-owner=${REPO_OWNER}"
  "--repo-name=${REPO_NAME}"
  "--branch-pattern=${BRANCH_PATTERN}"
  "--build-config=${BUILD_CONFIG}"
)

if [[ -n "${SERVICE_ACCOUNT:-}" ]]; then
  args+=("--service-account=${SERVICE_ACCOUNT}")
fi

if [[ "${INCLUDE_LOGS}" == "true" ]]; then
  args+=(--include-logs-with-status)
fi

echo "Creating Cloud Build trigger '${TRIGGER_NAME}' for ${REPO_OWNER}/${REPO_NAME} on ${BRANCH_PATTERN}..."
if ! output="$(gcloud "${args[@]}" 2>&1)"; then
  echo "${output}" >&2
  if [[ "${output}" == *"Repository mapping does not exist"* ]]; then
    echo >&2
    echo "Cloud Build cannot access this GitHub repo yet." >&2
    echo "Connect the repo here, then rerun this script:" >&2
    echo "${CONNECT_URL}" >&2
  fi
  exit 1
fi

echo "${output}"
echo "Trigger created. Pushes to main will now run ${BUILD_CONFIG} and deploy Cloud Run."
