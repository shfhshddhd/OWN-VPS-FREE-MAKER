#!/usr/bin/env bash
set -euo pipefail
: "${SUPERDMZ_TOKEN:?SUPERDMZ_TOKEN is required}"
curl -fsSL https://superdmz.com/download/LinuxInstaller.sh | sudo sh
sudo superdmz -add-token="$SUPERDMZ_TOKEN"
for i in $(seq 1 60); do
  out="$(sudo superdmz -status 2>&1 || true)"
  if printf '%s\n' "$out" | grep -qiE 'online|connected|active'; then
    echo "$out"
    exit 0
  fi
  sleep 2
done
sudo superdmz -status 2>&1 || true
exit 1
