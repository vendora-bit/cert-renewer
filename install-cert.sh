#!/usr/bin/env bash
set -euo pipefail

CERT_NAME="${CERTBOT_CERT_NAME:?CERTBOT_CERT_NAME is required}"
SOURCE_DIR="/etc/letsencrypt/live/${CERT_NAME}"
TARGET_DIR="${NGINX_CERT_TARGET_DIR:-/out}"
DOCKER_SOCKET="${DOCKER_SOCKET_PATH:-/var/run/docker.sock}"
NGINX_CONTAINER_NAME="${NGINX_CONTAINER_NAME:-nginx}"

install -d "${TARGET_DIR}"
cp "${SOURCE_DIR}/fullchain.pem" "${TARGET_DIR}/tls.crt"
cp "${SOURCE_DIR}/privkey.pem" "${TARGET_DIR}/tls.key"

curl --silent --show-error --fail \
  --unix-socket "${DOCKER_SOCKET}" \
  -X POST \
  "http://localhost/containers/${NGINX_CONTAINER_NAME}/kill?signal=HUP" >/dev/null

echo "Installed renewed certificate and reloaded ${NGINX_CONTAINER_NAME}"
