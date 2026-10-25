#!/bin/sh
set -eu

log_dir="${LOG_DIR:-/app/logs}"
data_dir="${ATTESTATION_DATA_DIR:-/app/data}"
# unset, the application would pick its own default (/logs), which appuser cannot create
export LOG_DIR="$log_dir" ATTESTATION_DATA_DIR="$data_dir"
mkdir -p "$log_dir" "$data_dir"
chown -R appuser:appuser "$log_dir" "$data_dir"
# departments.json there is the service's own state: only the service user may touch it
chmod 700 "$data_dir"

exec gosu appuser "$@"
