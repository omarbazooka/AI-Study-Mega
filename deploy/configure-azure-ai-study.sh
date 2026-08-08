#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-nabdak-rg}"
APP_NAME="${APP_NAME:-ai-study-api}"
STORAGE_BUCKET="${SUPABASE_STORAGE_BUCKET:-study-documents}"

if ! az account show >/dev/null 2>&1; then
  echo "Azure CLI is not signed in. Open Azure Cloud Shell or run: az login"
  exit 1
fi

if ! az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" >/dev/null 2>&1; then
  echo "Container App '$APP_NAME' was not found in resource group '$RESOURCE_GROUP'."
  echo "Deploy the backend container first, then run this script again."
  exit 1
fi

read -r -p "SUPABASE_URL: " SUPABASE_URL
read -s -r -p "SUPABASE_SERVICE_ROLE_KEY: " SUPABASE_SERVICE_ROLE_KEY
echo
read -s -r -p "GROQ_DEFAULT_API_KEY: " GROQ_DEFAULT_API_KEY
echo
read -r -p "CLOUDFLARE_ACCOUNT_ID: " CLOUDFLARE_ACCOUNT_ID
read -s -r -p "CLOUDFLARE_API_TOKEN: " CLOUDFLARE_API_TOKEN
echo
read -r -p "Frontend origin (use * until Vercel URL is ready): " CORS_ALLOWED_ORIGINS
CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-*}"

echo "Saving backend-only credentials as Azure Container App secrets..."
az containerapp secret set \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --secrets \
    supabase-service-role-key="$SUPABASE_SERVICE_ROLE_KEY" \
    groq-default-api-key="$GROQ_DEFAULT_API_KEY" \
    cloudflare-api-token="$CLOUDFLARE_API_TOKEN" \
  >/dev/null

echo "Configuring production environment variables and scale-to-zero..."
az containerapp update \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --set-env-vars \
    APP_ENV=production \
    AUTH_MODE=supabase \
    SUPABASE_URL="$SUPABASE_URL" \
    SUPABASE_SERVICE_ROLE_KEY=secretref:supabase-service-role-key \
    SUPABASE_STORAGE_BUCKET="$STORAGE_BUCKET" \
    GROQ_DEFAULT_API_KEY=secretref:groq-default-api-key \
    EMBEDDING_PROVIDER=cloudflare \
    CLOUDFLARE_ACCOUNT_ID="$CLOUDFLARE_ACCOUNT_ID" \
    CLOUDFLARE_API_TOKEN=secretref:cloudflare-api-token \
    CORS_ALLOWED_ORIGINS="$CORS_ALLOWED_ORIGINS" \
  --min-replicas 0 \
  --max-replicas 1 \
  >/dev/null

unset SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY GROQ_DEFAULT_API_KEY CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN CORS_ALLOWED_ORIGINS

FQDN=$(az containerapp show \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

echo
echo "Runtime configuration complete."
echo "Backend URL: https://${FQDN}"
echo "Health check: https://${FQDN}/"
