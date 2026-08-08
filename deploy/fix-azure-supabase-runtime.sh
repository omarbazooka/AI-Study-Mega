#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-nabdak-rg}"
APP_NAME="${APP_NAME:-ai-study-api}"
SUPABASE_URL="https://iobvuyfhqzwjuciaskhd.supabase.co"
FRONTEND_ORIGIN="https://ai-study-mega.vercel.app"
STORAGE_BUCKET="study-documents"

if ! az account show >/dev/null 2>&1; then
  echo "Azure CLI is not signed in. Open Azure Cloud Shell or run: az login"
  exit 1
fi

if ! az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" >/dev/null 2>&1; then
  echo "Container App '$APP_NAME' was not found in resource group '$RESOURCE_GROUP'."
  exit 1
fi

echo "Updating Azure backend to the active EDU Platform Supabase project."
echo "Supabase URL: $SUPABASE_URL"
echo "Frontend origin: $FRONTEND_ORIGIN"
echo
read -s -r -p "Current EDU Platform Supabase secret/service-role key: " SUPABASE_SECRET_KEY
echo

if [[ -z "$SUPABASE_SECRET_KEY" ]]; then
  echo "No Supabase secret key was entered. Nothing changed."
  exit 1
fi

echo "Saving the current Supabase backend key as an Azure Container App secret..."
az containerapp secret set \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --secrets supabase-service-role-key="$SUPABASE_SECRET_KEY" \
  >/dev/null

echo "Updating runtime variables..."
az containerapp update \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --set-env-vars \
    APP_ENV=production \
    AUTH_MODE=supabase \
    SUPABASE_URL="$SUPABASE_URL" \
    SUPABASE_SERVICE_ROLE_KEY=secretref:supabase-service-role-key \
    SUPABASE_STORAGE_BUCKET="$STORAGE_BUCKET" \
    CORS_ALLOWED_ORIGINS="$FRONTEND_ORIGIN" \
  --min-replicas 0 \
  --max-replicas 1 \
  >/dev/null

unset SUPABASE_SECRET_KEY

echo "Waiting for the newest revision to become ready..."
for _ in $(seq 1 30); do
  READY_REVISION=$(az containerapp show \
    -g "$RESOURCE_GROUP" \
    -n "$APP_NAME" \
    --query properties.latestReadyRevisionName \
    -o tsv 2>/dev/null || true)
  LATEST_REVISION=$(az containerapp show \
    -g "$RESOURCE_GROUP" \
    -n "$APP_NAME" \
    --query properties.latestRevisionName \
    -o tsv 2>/dev/null || true)
  if [[ -n "$LATEST_REVISION" && "$READY_REVISION" == "$LATEST_REVISION" ]]; then
    break
  fi
  sleep 3
done

FQDN=$(az containerapp show \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

LATEST_REVISION=$(az containerapp show \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --query properties.latestRevisionName \
  -o tsv)
READY_REVISION=$(az containerapp show \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --query properties.latestReadyRevisionName \
  -o tsv)

echo
echo "Azure Supabase runtime update complete."
echo "Latest revision: $LATEST_REVISION"
echo "Ready revision:  $READY_REVISION"
echo "Backend URL: https://$FQDN"
echo
echo "Health check:"
curl -fsS "https://$FQDN/" || true
echo
