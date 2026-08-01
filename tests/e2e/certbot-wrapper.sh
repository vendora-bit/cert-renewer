#!/bin/sh
set -eu

# Pebble validates the ACME flow. DNS provider behavior is covered by the
# production argument tests and does not require live Cloudflare credentials.
export REQUESTS_CA_BUNDLE=/test/pebble.minica.pem
exec /usr/local/bin/certbot certonly \
  --non-interactive \
  --agree-tos \
  --email integration@example.com \
  --manual \
  --preferred-challenges dns \
  --manual-auth-hook /bin/true \
  --manual-cleanup-hook /bin/true \
  --cert-name e2e.example \
  --config-dir /etc/letsencrypt \
  --work-dir /var/lib/letsencrypt \
  --logs-dir /var/log/letsencrypt \
  --server https://pebble:14000/dir \
  -d e2e.example \
  -d '*.e2e.example'
