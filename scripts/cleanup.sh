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
      printf '%s/%s\n' "$HOME" "${raw_path#"~/"}"
      ;;
    *)
      printf '%s\n' "$raw_path"
      ;;
  esac
}

trim_and_unquote() {
  local value="$1"

  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"

  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value#\"}"
    value="${value%\"}"
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value#\'}"
    value="${value%\'}"
  else
    value="${value%%[[:space:]]#*}"
    value="${value%"${value##*[![:space:]]}"}"
  fi

  printf '%s\n' "$value"
}

read_yaml_top_level_value() {
  local key="$1"

  awk -v key="$key" '
    /^[[:space:]]*#/ { next }
    $0 ~ "^" key ":[[:space:]]*" {
      line = $0
      sub("^" key ":[[:space:]]*", "", line)
      print line
      exit
    }
  ' "$CONFIG_FILE" 2>/dev/null || true
}

read_yaml_section_value() {
  local section="$1"
  local key="$2"

  awk -v section="$section" -v key="$key" '
    /^[[:space:]]*#/ { next }

    $0 ~ "^[[:space:]]*" section ":[[:space:]]*$" {
      in_section = 1
      next
    }

    in_section && $0 ~ "^[^[:space:]]" {
      in_section = 0
    }

    in_section && $0 ~ "^[[:space:]]+" key ":[[:space:]]*" {
      line = $0
      sub("^[[:space:]]+" key ":[[:space:]]*", "", line)
      print line
      exit
    }
  ' "$CONFIG_FILE" 2>/dev/null || true
}

configure_log_path() {
  local configured_dir=""
  local configured_file=""
  local raw_value=""

  if [[ -n "${WALLBUG_LOG_FILE:-}" ]]; then
    configured_file="$WALLBUG_LOG_FILE"
  elif [[ -n "${WALLBUG_LOGS_DIR:-}" ]]; then
    configured_dir="$WALLBUG_LOGS_DIR"
  elif [[ -r "$CONFIG_FILE" ]]; then
    raw_value="$(read_yaml_section_value "logging" "file")"
    configured_file="$(trim_and_unquote "$raw_value")"

    if [[ -z "$configured_file" ]]; then
      raw_value="$(read_yaml_section_value "paths" "logs_dir")"
      configured_dir="$(trim_and_unquote "$raw_value")"
    fi

    if [[ -z "$configured_dir" ]]; then
      raw_value="$(read_yaml_top_level_value "logs_dir")"
      configured_dir="$(trim_and_unquote "$raw_value")"
    fi
  fi

  if [[ -n "$configured_file" ]]; then
    LOG_FILE="$(expand_path "$configured_file")"
    LOG_DIR="$(dirname "$LOG_FILE")"
  elif [[ -n "$configured_dir" ]]; then
    LOG_DIR="$(expand_path "$configured_dir")"
    LOG_FILE="$LOG_DIR/wallbug.log"
  fi
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
  LOG_DIR="$(dirname "$LOG_FILE")"

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
