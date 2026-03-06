#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_NAME="$(basename "$0")"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '[%s] %s\n' "$SCRIPT_NAME" "$*"
}

error() {
  printf '[%s] ERROR: %s\n' "$SCRIPT_NAME" "$*" >&2
}

on_error() {
  local exit_code=$?
  local line_no=${1:-unknown}
  error "Cleanup failed at line ${line_no} (exit code ${exit_code})."
  exit "$exit_code"
}

on_interrupt() {
  error "Cleanup interrupted."
  exit 130
}

trap 'on_error $LINENO' ERR
trap 'on_interrupt' INT TERM

safe_remove() {
  local target="$1"

  if [[ -z "$target" ]]; then
    error "Refusing to remove an empty path."
    return 1
  fi

  if [[ ! -e "$target" ]]; then
    log "Skipping missing path: $target"
    return 0
  fi

  rm -rf -- "$target"
  log "Removed: $target"
}

main() {
  local log_dir="$PROJECT_ROOT/data/logs"
  local cache_dir="$PROJECT_ROOT/.cache"
  local tmp_dir="$PROJECT_ROOT/tmp"

  log "Starting cleanup in: $PROJECT_ROOT"

  safe_remove "$cache_dir"
  safe_remove "$tmp_dir"

  if [[ -d "$log_dir" ]]; then
    find "$log_dir" -type f -name '*.log' -delete
    log "Deleted .log files in: $log_dir"
  else
    log "Skipping missing log directory: $log_dir"
  fi

  log "Cleanup completed successfully."
}

main "$@"
