#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project id}"
: "${SUPABASE_URL:?Set SUPABASE_URL}"
: "${SUPABASE_SERVICE_ROLE_KEY:?Set SUPABASE_SERVICE_ROLE_KEY}"
: "${NEXT_PUBLIC_SUPABASE_ANON_KEY:?Set NEXT_PUBLIC_SUPABASE_ANON_KEY}"
: "${GROQ_API_KEY:?Set GROQ_API_KEY}"
: "${CLOUDFLARE_ACCOUNT_ID:?Set CLOUDFLARE_ACCOUNT_ID}"
: "${CLOUDFLARE_API_TOKEN:?Set CLOUDFLARE_API_TOKEN}"

REGION="${REGION:-europe-west1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-ai-study-api}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-ai-study-web}"
ARTIFACT_REPO="${ARTIFACT_REPO:-app-images}"
NEXT_PUBLIC_SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL:-$SUPABASE_URL}"
SUPABASE_STORAGE_BUCKET="${SUPABASE_STORAGE_BUCKET:-study-documents}"

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

BACKEND_ENV=(
  --set-env-vars "APP_ENV=production"
  --set-env-vars "AUTH_MODE=supabase"
  --set-env-vars "SUPABASE_URL=${SUPABASE_URL}"
  --set-env-vars "SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}"
  --set-env-vars "SUPABASE_STORAGE_BUCKET=${SUPABASE_STORAGE_BUCKET}"
  --set-env-vars "GROQ_API_KEY=${GROQ_API_KEY}"
  --set-env-vars "GROQ_DEFAULT_API_KEY=${GROQ_API_KEY}"
  --set-env-vars "EMBEDDING_PROVIDER=cloudflare"
  --set-env-vars "CLOUDFLARE_ACCOUNT_ID=${CLOUDFLARE_ACCOUNT_ID}"
  --set-env-vars "CLOUDFLARE_API_TOKEN=${CLOUDFLARE_API_TOKEN}"
  --set-env-vars "CORS_ALLOWED_ORIGINS=*"
)

if [[ -n "${SUPABASE_DB_PASSWORD:-}" ]]; then
  BACKEND_ENV+=(--set-env-vars "SUPABASE_DB_PASSWORD=${SUPABASE_DB_PASSWORD}")
fi
if [[ -n "${JINA_API_KEY:-}" ]]; then
  BACKEND_ENV+=(--set-env-vars "JINA_API_KEY=${JINA_API_KEY}")
fi
if [[ -n "${COHERE_API_KEY:-}" ]]; then
  BACKEND_ENV+=(--set-env-vars "COHERE_API_KEY=${COHERE_API_KEY}")
fi
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  BACKEND_ENV+=(--set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}")
fi

echo "Deploying AI Study backend..."
gcloud run deploy "${BACKEND_SERVICE}" \
  --source apps/backend \
  --region "${REGION}" \
  --allow-unauthenticated \
  --execution-environment gen2 \
  --cpu 1 \
  --memory 1Gi \
  --timeout 300 \
  --min 0 \
  --max 1 \
  "${BACKEND_ENV[@]}"

BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"
echo "Backend: ${BACKEND_URL}"

if ! gcloud artifacts repositories describe "${ARTIFACT_REPO}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${ARTIFACT_REPO}" \
    --repository-format=docker \
    --location "${REGION}" \
    --description="Application images"
fi

FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${FRONTEND_SERVICE}:latest"

echo "Building AI Study frontend with Cloud Run backend URL..."
gcloud builds submit apps/Frontend \
  --config apps/Frontend/cloudbuild.yaml \
  --substitutions "_IMAGE=${FRONTEND_IMAGE},_NEXT_PUBLIC_API_URL=${BACKEND_URL},_NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL},_NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY}"

echo "Deploying AI Study frontend..."
gcloud run deploy "${FRONTEND_SERVICE}" \
  --image "${FRONTEND_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --execution-environment gen2 \
  --cpu 1 \
  --memory 512Mi \
  --timeout 300 \
  --min 0 \
  --max 1

FRONTEND_URL="$(gcloud run services describe "${FRONTEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"

echo "Restricting backend CORS to ${FRONTEND_URL}..."
gcloud run services update "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --update-env-vars "CORS_ALLOWED_ORIGINS=${FRONTEND_URL}" >/dev/null

echo
echo "Cloud Run deployment complete."
echo "AI Study frontend: ${FRONTEND_URL}"
echo "AI Study backend:  ${BACKEND_URL}"
