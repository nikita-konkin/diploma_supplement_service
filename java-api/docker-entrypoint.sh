#!/bin/sh
set -eu

log_dir="${LOG_DIR:-/app/logs}"
mkdir -p "$log_dir"
chown -R appuser:appgroup "$log_dir"

exec su-exec appuser:appgroup "$@"
