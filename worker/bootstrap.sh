#!/usr/bin/env bash
set -Eeuo pipefail

: "${VPS_ROOT:=/opt/vps-data}"
: "${SSH_PASSWORD:?SSH_PASSWORD is required}"

log(){ echo "[bootstrap] $*"; }
fail(){
  rc=$?
  echo "::error::Bootstrap failed (exit $rc) at line ${BASH_LINENO[0]}: ${BASH_COMMAND}"
  echo "::group::System diagnostics"
  uname -a || true
  cat /etc/os-release || true
  echo "--- disk ---"; df -h / || true
  echo "--- memory ---"; free -h || true
  echo "--- services ---"; sudo systemctl --no-pager --full status ssh docker || true
  echo "--- journal ---"; sudo journalctl -u ssh -u docker -n 80 --no-pager || true
  echo "--- apt ---"; sudo dpkg --audit || true
  echo "::endgroup"
  exit "$rc"
}
trap fail ERR

test "${#SSH_PASSWORD}" -ge 16 || { echo "::error::SSH_PASSWORD must be at least 16 characters"; exit 1; }

log "OS: $(. /etc/os-release && echo "$PRETTY_NAME")"
log "Runner: $(uname -m)"

log "Updating apt metadata"
sudo apt-get update -y

packages=(
  openssh-server curl jq git rsync ca-certificates python3-venv
  netcat-openbsd docker.io
)

log "Installing base packages"
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"

# docker-compose-v2 is useful but must not make the whole VPS fail if the
# Ubuntu image/repository does not currently expose that package.
if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
  log "Installing docker-compose-v2"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends docker-compose-v2
else
  log "docker-compose-v2 package unavailable; checking Docker Compose plugin"
fi

log "Verifying required binaries"
command -v sshd
command -v docker
command -v python3
command -v rsync
command -v nc

log "Starting SSH and Docker"
sudo systemctl enable --now ssh
sudo systemctl enable --now docker

log "Setting root password"
printf 'root:%s\n' "$SSH_PASSWORD" | sudo chpasswd
sudo usermod -U root

log "Writing SSH configuration"
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

log "Validating SSH configuration"
sudo sshd -t

log "Restarting SSH"
sudo systemctl restart ssh
sudo systemctl is-active --quiet ssh

log "Preparing VPS data root"
sudo install -d -m 755 "$VPS_ROOT"

log "Verifying Docker daemon"
sudo systemctl is-active --quiet docker
sudo docker info >/dev/null

log "Verifying Docker Compose"
if docker compose version >/dev/null 2>&1; then
  docker compose version
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose version
else
  echo "::error::Docker Compose is unavailable after bootstrap"
  exit 1
fi

log "Bootstrap verification complete"
echo "BOOTSTRAP_READY=YES"
