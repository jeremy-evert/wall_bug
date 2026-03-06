#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_NAME="$(basename "$0")"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${WALLBUG_CONFIG_FILE:-$PROJECT_ROOT/config.yaml}"

LOG_DIR="$PROJECT_ROOT/data/logs"
LOG_FILE="$LOG_DIR/wallbug.log"

timestamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

expand_path() {
  local raw_path="$1"
  case "$raw_path" in
    "~")
      printf '%s\n' "$HOME"
      ;;
    "~/"*)
      printf '%s/%s\n' "$HOME" "${raw_path#~/}"
      ;;
    *)
      printf '%s\n' "$raw_path"
      ;;
  esac
}

configure_log_path() {
  local configured=""

  if [[ -n "${WALLBUG_LOGS_DIR:-}" ]]; then
    configured="$WALLBUG_LOGS_DIR"
  elif [[ -r "$CONFIG_FILE" ]]; then
    configured="$(awk '/^[[:space:]]*logs_dir:[[:space:]]*/ {print $2; exit}' "$CONFIG_FILE" 2>/dev/null || true)"
    configured="${configured#\"}"
    configured="${configured%\"}"
    configured="${configured#\'}"
    configured="${configured%\'}"
  fi

  if [[ -n "$configured" ]]; then
    LOG_DIR="$(expand_path "$configured")"
  fi

  LOG_FILE="$LOG_DIR/wallbug.log"
}

write_log() {
  local level="$1"
  shift
  local message="$*"
  local console_line
  local file_line

  case "$level" in
    INFO)
      console_line="[$SCRIPT_NAME] $message"
      ;;
    *)
      console_line="[$SCRIPT_NAME] $level: $message"
      ;;
  esac

  file_line="[$(timestamp)] [$SCRIPT_NAME] [$level] $message"

  if [[ "$level" == "ERROR" ]]; then
    printf '%s\n' "$console_line" >&2
  else
    printf '%s\n' "$console_line"
  fi

  if [[ -n "${LOG_FILE:-}" ]]; then
    printf '%s\n' "$file_line" >> "$LOG_FILE" 2>/dev/null || true
  fi
}

log() {
  write_log "INFO" "$*"
}

warn() {
  write_log "WARN" "$*"
}

error() {
  write_log "ERROR" "$*"
}

init_logging() {
  if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    LOG_FILE=""
    warn "Unable to create log directory: $LOG_DIR. Continuing without file logging."
    return 0
  fi

  if ! touch "$LOG_FILE" 2>/dev/null; then
    LOG_FILE=""
    warn "Unable to write to log file in $LOG_DIR. Continuing without file logging."
    return 0
  fi
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

cleanup_log_files() {
  if [[ ! -d "$LOG_DIR" ]]; then
    log "Skipping missing log directory: $LOG_DIR"
    return 0
  fi

  local find_status=0

  if [[ -n "${LOG_FILE:-}" ]]; then
    find "$LOG_DIR" -type f -name '*.log' ! -samefile "$LOG_FILE" -delete || find_status=$?
  else
    find "$LOG_DIR" -type f -name '*.log' -delete || find_status=$?
  fi

  if [[ $find_status -ne 0 ]]; then
    warn "Encountered errors while deleting .log files in: $LOG_DIR"
    return 0
  fi

  log "Deleted .log files in: $LOG_DIR"
}

main() {
  local cache_dir="$PROJECT_ROOT/.cache"
  local tmp_dir="$PROJECT_ROOT/tmp"

  configure_log_path
  init_logging
  log "Starting cleanup in: $PROJECT_ROOT"

  safe_remove "$cache_dir"
  safe_remove "$tmp_dir"
  cleanup_log_files

  log "Cleanup completed successfully."
}

main "$@"
