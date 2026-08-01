# systemd: dedicated service identity

The maintained unit and installer live in the repository's `systemd/`
directory. Install from a checked-out release:

```bash
sudo ./systemd/install.sh
sudoedit /etc/cert-renewer/config.toml
sudo install -o root -g cert-renewer -m 0640 /path/to/cloudflare-token /run/secrets/cloudflare-example
sudo ./systemd/install.sh --enable
systemctl status cert-renewer
```

The installer preserves an existing configuration. The service has
`ProtectSystem=strict`, a dedicated `cert-renewer` user and a restricted
system-call/address-family set. If your destination is outside the default
allowlist, add a deliberate systemd drop-in for that path and grant write access
only to the service user.

