# HAProxy: assemble a PEM bundle outside the renewer

HAProxy commonly consumes one PEM file containing both the certificate chain and
private key. cert-renewer deliberately installs separate files atomically.

Use a small host-owned deployment helper triggered by your normal operations
tooling after a successful cycle:

```sh
#!/bin/sh
set -eu
src=/srv/certificates/example.com/current
tmp=/etc/haproxy/certs/example.com.pem.tmp
cat "$src/fullchain.pem" "$src/privkey.pem" > "$tmp"
chmod 0600 "$tmp"
mv -f "$tmp" /etc/haproxy/certs/example.com.pem
systemctl reload haproxy
```

The renewer needs access only to `/srv/certificates`; the host helper owns the
HAProxy path and reload privilege. Validate the helper under your service
account before wiring it into `[certificates.reload]`.

