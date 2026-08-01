#!/bin/sh
set -eu

export SSL_CERT_FILE=/test/pebble.minica.pem
attempt=0
until python -c 'import urllib.request; urllib.request.urlopen("https://pebble:14000/dir", timeout=2).read()' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Pebble did not become ready" >&2
    exit 1
  fi
  sleep 1
done

python -m cert_renewer once --config /test/config.toml
test -L /certificates/e2e.example/current
test -L /certificates/e2e.example/fullchain.pem
test -L /certificates/e2e.example/privkey.pem
openssl x509 -in /certificates/e2e.example/current/fullchain.pem -noout -checkend 60
python -m cert_renewer health --config /test/config.toml
