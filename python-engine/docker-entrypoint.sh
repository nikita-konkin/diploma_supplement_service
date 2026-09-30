#!/bin/sh
set -eu

log_dir="${LOG_DIR:-/app/logs}"
# unset, the application would pick its own default (/logs), which appuser cannot create
export LOG_DIR="$log_dir"
mkdir -p "$log_dir"
chown -R appuser:appuser "$log_dir"

exec gosu appuser "$@"
