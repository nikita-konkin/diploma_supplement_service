#!/bin/sh
set -eu

log_dir="${LOG_DIR:-/app/logs}"
mkdir -p "$log_dir"
chown -R appuser:appuser "$log_dir"

exec gosu appuser "$@"
