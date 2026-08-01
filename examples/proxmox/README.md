# Proxmox: host-side certificate deployment

Use cert-renewer for the ACME lifecycle, but keep Proxmox ownership and reload
rights in a root-owned, narrowly scoped helper. First issue to a neutral
destination such as `/srv/certificates/proxmox.example.com`. Then inspect and
copy only the active revision:

```sh
#!/bin/sh
set -eu
src=/srv/certificates/proxmox.example.com/current
install -m 0644 "$src/fullchain.pem" /etc/pve/local/pveproxy-ssl.pem
install -m 0600 "$src/privkey.pem" /etc/pve/local/pveproxy-ssl.key
pveproxy restart
```

Confirm the exact target paths and recommended reload command against the
Proxmox version you operate. Test through an out-of-band console first: an
incorrect certificate deployment can interrupt web UI access. The container
does not need Docker socket or Proxmox root access.

