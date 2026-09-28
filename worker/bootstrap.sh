#!/usr/bin/env bash
set -euo pipefail

: "${VPS_ROOT:=/opt/vps-data}"
: "${SSH_PASSWORD:?SSH_PASSWORD is required}"

sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  openssh-server curl jq git rsync ca-certificates python3-venv \
  netcat-openbsd docker.io docker-compose-v2

sudo systemctl enable --now ssh
sudo systemctl enable --now docker

test "${#SSH_PASSWORD}" -ge 16 || { echo "SSH_PASSWORD must be at least 16 characters"; exit 1; }
printf 'root:%s\n' "$SSH_PASSWORD" | sudo chpasswd
sudo usermod -U root

sudo install -d -m 755 /etc/ssh/sshd_config.d
sudo tee /etc/ssh/sshd_config.d/99-own-vps.conf >/dev/null <<'EOF'
PermitRootLogin yes
PasswordAuthentication yes
KbdInteractiveAuthentication no
PubkeyAuthentication no
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding no
AllowTcpForwarding yes
ClientAliveInterval 60
ClientAliveCountMax 3
MaxAuthTries 3
LoginGraceTime 20
EOF

sudo sshd -t
sudo systemctl restart ssh
sudo systemctl is-active --quiet ssh

sudo mkdir -p "$VPS_ROOT"
sudo chmod 755 "$VPS_ROOT"
sudo docker info >/dev/null
