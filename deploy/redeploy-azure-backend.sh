#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-nabdak-rg}"
APP_NAME="${APP_NAME:-ai-study-api}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/apps/backend"
TAG="cf-fallback-$(date -u +%Y%m%d%H%M%S)"

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI is not available. Run this from Azure Cloud Shell."
  exit 1
fi

if ! az account show >/dev/null 2>&1; then
  echo "Azure CLI is not signed in. Open Azure Cloud Shell or run: az login"
  exit 1
fi

az extension add --name containerapp --upgrade --yes >/dev/null 2>&1 || true

if ! az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" >/dev/null 2>&1; then
  echo "Container App '$APP_NAME' was not found in resource group '$RESOURCE_GROUP'."
  exit 1
fi

if [[ ! -f "$BACKEND_DIR/Dockerfile" ]]; then
  echo "Backend Dockerfile was not found at: $BACKEND_DIR/Dockerfile"
  exit 1
fi

CURRENT_IMAGE="$(az containerapp show \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --query 'properties.template.containers[0].image' \
  -o tsv)"

if [[ -z "$CURRENT_IMAGE" ]]; then
  echo "Could not determine the current Azure Container App image."
  exit 1
fi

echo "Current image: $CURRENT_IMAGE"
echo "Building backend from: $BACKEND_DIR"

REGISTRY_SERVER="${CURRENT_IMAGE%%/*}"

if [[ "$REGISTRY_SERVER" == *.azurecr.io ]]; then
  ACR_NAME="${REGISTRY_SERVER%%.*}"
  IMAGE_PATH="${CURRENT_IMAGE#*/}"
  IMAGE_REPOSITORY="${IMAGE_PATH%@*}"
  IMAGE_REPOSITORY="${IMAGE_REPOSITORY%:*}"
  NEW_IMAGE="$REGISTRY_SERVER/$IMAGE_REPOSITORY:$TAG"

  echo "Using existing Azure Container Registry: $ACR_NAME"
  echo "New image: $NEW_IMAGE"

  az acr show -n "$ACR_NAME" >/dev/null
  az acr build \
    --registry "$ACR_NAME" \
    --image "$IMAGE_REPOSITORY:$TAG" \
    "$BACKEND_DIR"

  echo "Updating Container App image without replacing runtime secrets/env vars..."
  az containerapp update \
    -g "$RESOURCE_GROUP" \
    -n "$APP_NAME" \
    --image "$NEW_IMAGE" \
    >/dev/null
else
  MANAGED_ENV_ID="$(az containerapp show \
    -g "$RESOURCE_GROUP" \
    -n "$APP_NAME" \
    --query properties.managedEnvironmentId \
    -o tsv)"

  if [[ -z "$MANAGED_ENV_ID" ]]; then
    echo "Could not determine the Container Apps environment."
    exit 1
  fi

  echo "Current image is not hosted in ACR; redeploying from local source with containerapp up."
  az containerapp up \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$MANAGED_ENV_ID" \
    --source "$BACKEND_DIR" \
    --ingress external \
    --target-port 8080 \
    >/dev/null
fi

echo "Waiting for the new revision to become ready..."
for _ in $(seq 1 80); do
  LATEST_REVISION="$(az containerapp show \
    -g "$RESOURCE_GROUP" \
    -n "$APP_NAME" \
    --query properties.latestRevisionName \
    -o tsv 2>/dev/null || true)"
  READY_REVISION="$(az containerapp show \
    -g "$RESOURCE_GROUP" \
    -n "$APP_NAME" \
    --query properties.latestReadyRevisionName \
    -o tsv 2>/dev/null || true)"

  if [[ -n "$LATEST_REVISION" && "$LATEST_REVISION" == "$READY_REVISION" ]]; then
    break
  fi
  sleep 5
done

LATEST_REVISION="$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.latestRevisionName -o tsv)"
READY_REVISION="$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.latestReadyRevisionName -o tsv)"
FQDN="$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"
DEPLOYED_IMAGE="$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query 'properties.template.containers[0].image' -o tsv)"

echo
echo "Azure backend redeploy complete."
echo "Latest revision: $LATEST_REVISION"
echo "Ready revision:  $READY_REVISION"
echo "Image:           $DEPLOYED_IMAGE"
echo "Backend URL:     https://$FQDN"
echo
echo "Health check:"
curl -fsS --retry 5 --retry-delay 2 "https://$FQDN/"
echo

if [[ "$LATEST_REVISION" != "$READY_REVISION" ]]; then
  echo "WARNING: the latest revision is not the ready revision. Inspect Azure revision logs before using production."
  exit 2
fi
