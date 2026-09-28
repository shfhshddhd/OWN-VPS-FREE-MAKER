#!/usr/bin/env bash
set -euo pipefail
sudo systemctl is-active --quiet ssh
sudo systemctl is-active --quiet docker
sudo ss -lntp | grep -q ':22 '
test -d "${VPS_ROOT:-/opt/vps-data}"
