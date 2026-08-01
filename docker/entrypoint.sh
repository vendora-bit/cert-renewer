#!/bin/sh
set -eu

# Keep `docker run ghcr.io/vendora-bit/cert-renewer:latest check` useful: the
# documented configuration mount lives at /config, while systemd continues to
# provide its explicit /etc path. Do not append a second config argument when a
# caller intentionally supplied one.
case " $* " in
  *" --config "* | *" --config="*) ;;
  *) set -- "$@" --config /config/config.toml ;;
esac

exec python -m cert_renewer "$@"
