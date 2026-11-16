#!/usr/bin/env bash
# Package only public static output; never upload the entire build working directory.
set -euo pipefail
site=${1:?public site directory required}
artifact=${2:?new artifact directory required}
scripts=$(cd "$(dirname "$0")" && pwd)
[[ -d "$site" && ! -L "$site" && -s "$site/index.html" ]]
[[ "${RELEASE_ID:?release id required}" =~ ^[a-zA-Z0-9_-]+$ ]]
[[ ! -e "$artifact" && ! -L "$artifact" ]]
[[ -z "$(find "$site" ! -type f ! -type d -print -quit)" ]]
# Fail on obvious credentials/repository metadata. Project tests must also inspect build-time secrets.
[[ -z "$(find "$site" \( -name '.env*' -o -name '.git' -o -name '.ssh' -o -name '.centaur' -o -name '*.pem' -o -name '*.key' -o -name 'id_rsa*' -o -name 'id_ed25519*' \) -print -quit)" ]]
mkdir "$artifact"
cp -R "$site" "$artifact/site"
printf '%s\n' "$RELEASE_ID" > "$artifact/site/centaur-release.txt"
cp "$scripts/activate-static.sh" "$scripts/retry-transfer.sh" "$artifact/"
cd "$artifact"
find site -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
sha256sum activate-static.sh retry-transfer.sh >> SHA256SUMS
