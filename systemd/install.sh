#!/bin/sh
set -eu

ENABLE=false
if [ "${1:-}" = "--enable" ]; then
  ENABLE=true
elif [ "$#" -ne 0 ]; then
  echo "usage: $0 [--enable]" >&2
  exit 2
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "install.sh must run as root" >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
APP_DIR=/opt/cert-renewer
CONFIG_DIR=/etc/cert-renewer
CONFIG_PATH=$CONFIG_DIR/config.toml

install -d -m 0755 "$APP_DIR/src" "$CONFIG_DIR"
rm -rf "$APP_DIR/src/cert_renewer"
cp -R "$PROJECT_DIR/src/cert_renewer" "$APP_DIR/src/cert_renewer"
find "$APP_DIR/src/cert_renewer" -type d -exec chmod 0755 {} +
find "$APP_DIR/src/cert_renewer" -type f -exec chmod 0644 {} +
install -m 0644 "$PROJECT_DIR/systemd/cert-renewer.service" /etc/systemd/system/cert-renewer.service

if [ ! -e "$CONFIG_PATH" ]; then
  install -m 0600 "$PROJECT_DIR/examples/config.toml" "$CONFIG_PATH"
fi

systemctl daemon-reload
if [ "$ENABLE" = true ]; then
  PYTHONPATH="$APP_DIR/src" python3 -m cert_renewer check --config "$CONFIG_PATH"
  systemctl enable --now cert-renewer.service
fi

echo "Installed cert-renewer. Configure $CONFIG_PATH and run: systemctl restart cert-renewer"
