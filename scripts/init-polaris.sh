#!/bin/sh

set -eu

POLARIS_URL="${POLARIS_URL:-http://polaris:8181}"
CLIENT_ID="${CLIENT_ID:-root}"
CLIENT_SECRET="${CLIENT_SECRET:-s3cr3t}"
CATALOG_NAME="${CATALOG_NAME:-lakehouse}"
POLARIS_REALM="${POLARIS_REALM:-POLARIS}"

echo "Initializing Apache Polaris..."

echo "Obtaining OAuth token..."

TOKEN_RESPONSE=$(
  curl \
    --fail-with-body \
    --silent \
    --show-error \
    -X POST \
    "${POLARIS_URL}/api/catalog/v1/oauth/tokens" \
    -H "Polaris-Realm: ${POLARIS_REALM}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials" \
    -d "client_id=${CLIENT_ID}" \
    -d "client_secret=${CLIENT_SECRET}" \
    -d "scope=PRINCIPAL_ROLE:ALL"
)

TOKEN=$(echo "${TOKEN_RESPONSE}" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "${TOKEN}" ]; then
  echo "Could not obtain Polaris access token"
  echo "${TOKEN_RESPONSE}"
  exit 1
fi

echo "OAuth token obtained"

echo "Checking catalog '${CATALOG_NAME}'..."

STATUS=$(
  curl \
    --silent \
    --output /dev/null \
    --write-out "%{http_code}" \
    -H "Polaris-Realm: ${POLARIS_REALM}" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${POLARIS_URL}/api/management/v1/catalogs/${CATALOG_NAME}"
)

if [ "${STATUS}" = "200" ]; then
  echo "Catalog '${CATALOG_NAME}' already exists"
  exit 0
fi

echo "Creating catalog '${CATALOG_NAME}'..."

curl \
  --fail-with-body \
  -X POST \
  "${POLARIS_URL}/api/management/v1/catalogs" \
  -H "Polaris-Realm: ${POLARIS_REALM}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"catalog\": {
      \"name\": \"${CATALOG_NAME}\",
      \"type\": \"INTERNAL\",
      \"properties\": {
        \"default-base-location\": \"s3://warehouse\"
      },
      \"storageConfigInfo\": {
        \"storageType\": \"S3\",
        \"allowedLocations\": [
          \"s3://warehouse\"
        ]
      }
    }
  }"

echo
echo "Catalog '${CATALOG_NAME}' created"

echo "Granting catalog management privileges..."

curl \
  --fail-with-body \
  -X PUT \
  "${POLARIS_URL}/api/management/v1/catalogs/${CATALOG_NAME}/catalog-roles/catalog_admin/grants" \
  -H "Polaris-Realm: ${POLARIS_REALM}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "catalog",
    "privilege": "CATALOG_MANAGE_CONTENT"
  }'

echo
echo "Polaris initialization complete."