#!/usr/bin/env bash
# Retry only an idempotent transfer, never activation or database migrations.
set -euo pipefail
for attempt in 1 2 3; do
  if "$@"; then exit 0; fi
  if [[ "$attempt" == 3 ]]; then
    echo 'Transfer failed after 3 attempts' >&2
    exit 1
  fi
  sleep "$((attempt * 5))"
done
