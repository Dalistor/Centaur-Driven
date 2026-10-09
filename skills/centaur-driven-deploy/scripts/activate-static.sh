#!/usr/bin/env bash
# Linux static releases: existing web server serves ROOT/current without restarting.
set -Eeuo pipefail
root=${1:?release root required}
release_id=${2:?release id required}
health_url=${3:?public release-marker URL required}
[[ "$root" =~ ^/[a-zA-Z0-9_/-]+$ && "$root" != / && "$release_id" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
[[ "$health_url" == http://* || "$health_url" == https://* ]] || exit 2
[[ "$(readlink -f "$root")" == "$root" && ! -L "$root/releases" ]] || { echo 'Release root must be canonical and isolated' >&2; exit 2; }
release="$root/releases/$release_id"
[[ -d "$release/site" && ! -L "$release" && -L "$root/current" ]] || { echo 'Existing current symlink and isolated release required' >&2; exit 2; }
[[ ! -L "$release/site" && ! -L "$root/.deploy.lock" && -z "$(find "$release" -type l -print -quit)" ]] || { echo 'Symlinks inside releases are not supported' >&2; exit 2; }
exec 9>>"$root/.deploy.lock"
flock -n 9 || { echo 'Another activation is running' >&2; exit 1; }
previous=$(readlink -f "$root/current")
[[ -d "$previous" && "$previous" == "$root"/releases/*/site && "$previous" != "$release/site" ]] || { echo 'Current release is invalid or already active' >&2; exit 2; }
previous_id=$(cat "$previous/centaur-release.txt")
[[ -n "$previous_id" && "$(curl --fail --silent --show-error --max-time 10 "$health_url")" == "$previous_id" ]] || { echo 'Previous release health failed; activation blocked' >&2; exit 1; }
(cd "$release" && sha256sum --check SHA256SUMS)
[[ -s "$release/site/index.html" && "$(cat "$release/site/centaur-release.txt")" == "$release_id" ]] || exit 1
candidate_pid=''
switched=false
complete=false
next="$root/.current-$release_id"
cleanup() {
  code=$?
  trap - EXIT INT TERM HUP
  if [[ "$switched" == true && "$complete" != true ]]; then
    ln -sfn "$previous" "$next"
    mv -Tf "$next" "$root/current"
    echo 'Activation failed; previous release restored' >&2
    # Verify restoration through the same serving path; keep failure exit status.
    expected=$(cat "$previous/centaur-release.txt" 2>/dev/null || true)
    if [[ -n "$expected" ]]; then
      actual=$(curl --fail --silent --show-error --max-time 10 "$health_url" || true)
      [[ "$actual" == "$expected" ]] || echo 'Rollback health failed: operator intervention required' >&2
    fi
  fi
  [[ -z "$candidate_pid" ]] || { kill "$candidate_pid" 2>/dev/null || true; wait "$candidate_pid" 2>/dev/null || true; }
  rm -f "$next"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
# Bind an OS-assigned loopback port, avoiding collisions and checking actual HTTP serving.
python3 - "$release/site" "$release/candidate-port" <<'PY' &
import functools, http.server, pathlib, sys
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=sys.argv[1])
with http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
    pathlib.Path(sys.argv[2]).write_text(str(server.server_port))
    server.serve_forever()
PY
candidate_pid=$!
for attempt in {1..30}; do
  [[ ! -f "$release/candidate-port" ]] || break
  kill -0 "$candidate_pid"
  sleep 0.1
done
port=$(cat "$release/candidate-port")
curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:$port/index.html" >/dev/null
[[ "$(curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:$port/centaur-release.txt")" == "$release_id" ]]
ln -s "$release/site" "$next"
# Set the rollback flag first so even a signal immediately after rename restores the old target.
switched=true
mv -Tf "$next" "$root/current"
for attempt in {1..10}; do
  if [[ "$(curl --fail --silent --show-error --max-time 10 "$health_url" || true)" == "$release_id" ]]; then
    complete=true
    break
  fi
  sleep 1
done
[[ "$complete" == true ]] || exit 1
printf 'Activated %s; retained previous release %s\n' "$release_id" "$previous"
# Retention is deliberately separate: active/previous versions and shared data are never deleted here.
