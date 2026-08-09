#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-nabdak-rg}"
APP_NAME="${APP_NAME:-ai-study-api}"
IMAGE="${IMAGE:-ghcr.io/omarbazooka/ai-study-api:azure-latest}"

if ! az account show >/dev/null 2>&1; then
  echo "Azure CLI is not signed in. Use Azure Cloud Shell or run az login."
  exit 1
fi

if ! az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" >/dev/null 2>&1; then
  echo "Container App '$APP_NAME' was not found in resource group '$RESOURCE_GROUP'."
  exit 1
fi

echo "Switching Azure Container App to prebuilt GitHub Container Registry image."
echo "Image: $IMAGE"

az containerapp update \
  -g "$RESOURCE_GROUP" \
  -n "$APP_NAME" \
  --image "$IMAGE" \
  >/dev/null

echo "Waiting for the newest revision to become ready..."
for _ in $(seq 1 40); do
  READY_REVISION=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.latestReadyRevisionName -o tsv 2>/dev/null || true)
  LATEST_REVISION=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.latestRevisionName -o tsv 2>/dev/null || true)
  if [[ -n "$LATEST_REVISION" && "$READY_REVISION" == "$LATEST_REVISION" ]]; then
    break
  fi
  sleep 3
done

LATEST_REVISION=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.latestRevisionName -o tsv)
READY_REVISION=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.latestReadyRevisionName -o tsv)
FQDN=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)
RUNNING_IMAGE=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" --query 'properties.template.containers[0].image' -o tsv)

echo
echo "Azure image switch complete."
echo "Latest revision: $LATEST_REVISION"
echo "Ready revision:  $READY_REVISION"
echo "Running image:   $RUNNING_IMAGE"
echo "Backend URL:     https://$FQDN"
echo "Health check:"
curl -fsS "https://$FQDN/" || true
echo

if [[ "$LATEST_REVISION" != "$READY_REVISION" ]]; then
  echo "WARNING: The new revision is not ready. If Azure reports UNAUTHORIZED while pulling GHCR, make the ai-study-api package public in GitHub Packages and rerun this script."
  exit 2
fi
