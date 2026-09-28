#!/usr/bin/env bash
set -euo pipefail
out="$(sudo superdmz -status 2>&1 || true)"
printf '%s\n' "$out"
printf '%s\n' "$out" | grep -qiE 'online|connected|active'
