#!/bin/sh
set -eu

exec python -m cert_renewer "$@"
