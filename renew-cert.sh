#!/usr/bin/env bash
set -euo pipefail

CERT_NAME="${CERTBOT_CERT_NAME:?CERTBOT_CERT_NAME is required}"
PRIMARY_DOMAIN="${CERTBOT_PRIMARY_DOMAIN:?CERTBOT_PRIMARY_DOMAIN is required}"
EXTRA_DOMAINS_RAW="${CERTBOT_EXTRA_DOMAINS:?CERTBOT_EXTRA_DOMAINS is required}"
CHECK_INTERVAL="${CERTBOT_RENEW_INTERVAL_SECONDS:-43200}"
PROPAGATION_SECONDS="${CERTBOT_PROPAGATION_SECONDS:-90}"
STATE_DIR="${CERTBOT_STATE_DIR:-/var/lib/cert-renewer}"
TOKEN_FILE="${CLOUDFLARE_API_TOKEN_FILE:-/run/secrets/cloudflare_api_token}"
CREDS_FILE="/tmp/cloudflare.ini"

mkdir -p "${STATE_DIR}"
printf 'dns_cloudflare_api_token = %s\n' "$(cat "${TOKEN_FILE}")" > "${CREDS_FILE}"
chmod 600 "${CREDS_FILE}"

build_domain_args() {
  local args=("-d" "${PRIMARY_DOMAIN}")
  IFS=',' read -r -a extras <<< "${EXTRA_DOMAINS_RAW}"
  for raw in "${extras[@]}"; do
    local domain
    domain="$(printf '%s' "${raw}" | xargs)"
    [ -n "${domain}" ] || continue
    args+=("-d" "${domain}")
  done
  printf '%s\0' "${args[@]}"
}

run_certbot() {
  mapfile -d '' domain_args < <(build_domain_args)

  certbot certonly \
    --non-interactive \
    --agree-tos \
    --register-unsafely-without-email \
    --keep-until-expiring \
    --dns-cloudflare \
    --dns-cloudflare-credentials "${CREDS_FILE}" \
    --dns-cloudflare-propagation-seconds "${PROPAGATION_SECONDS}" \
    --config-dir /etc/letsencrypt \
    --work-dir /var/lib/letsencrypt \
    --logs-dir /var/log/letsencrypt \
    --cert-name "${CERT_NAME}" \
    --deploy-hook /usr/local/bin/install-cert.sh \
    "${domain_args[@]}"

  date +%s > "${STATE_DIR}/.last-success"
}

while true; do
  if run_certbot; then
    sleep "${CHECK_INTERVAL}"
  else
    echo "Certificate renewal failed, retrying in 300 seconds" >&2
    sleep 300
  fi
done
