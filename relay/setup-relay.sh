#!/usr/bin/env bash
set -euo pipefail

# Run this on the permanent Ubuntu relay VM as root.
# It creates:
#   relay-tunnel   -> reverse SSH tunnel account
#   relay-control  -> restricted handover control account
# HAProxy listens publicly on TCP/2222 and forwards to the active loopback tunnel.

apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server haproxy netcat-openbsd

id relay-tunnel >/dev/null 2>&1 || useradd --create-home --shell /usr/sbin/nologin relay-tunnel
id relay-control >/dev/null 2>&1 || useradd --create-home --shell /bin/bash relay-control

install -d -m 700 /home/relay-tunnel/.ssh /home/relay-control/.ssh /etc/own-vps
touch /home/relay-tunnel/.ssh/authorized_keys /home/relay-control/.ssh/authorized_keys
chmod 600 /home/relay-tunnel/.ssh/authorized_keys /home/relay-control/.ssh/authorized_keys
chown -R relay-tunnel:relay-tunnel /home/relay-tunnel/.ssh
chown -R relay-control:relay-control /home/relay-control/.ssh

cat >/etc/haproxy/haproxy.cfg <<'EOF'
global
    log /dev/log local0
    log /dev/log local1 notice
    daemon
    stats socket /run/haproxy/admin.sock mode 660 level admin

defaults
    log global
    mode tcp
    timeout connect 5s
    timeout client  2h
    timeout server  2h

frontend ssh_public
    bind :2222
    default_backend ssh_active

backend ssh_active
    mode tcp
    option tcp-check
    server active 127.0.0.1:29999 check inter 2s fall 2 rise 1
EOF

cat >/usr/local/sbin/activate-vps-backend <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
port="${1:-}"
[[ "$port" =~ ^2[0-9]{4}$ ]] || { echo "invalid backend port" >&2; exit 2; }
(( port >= 20000 && port <= 29999 )) || { echo "backend port out of range" >&2; exit 2; }
nc -z 127.0.0.1 "$port" || { echo "backend tunnel is not reachable" >&2; exit 3; }

sed -i -E "s#server active 127.0.0.1:[0-9]+#server active 127.0.0.1:${port}#" /etc/haproxy/haproxy.cfg
haproxy -c -f /etc/haproxy/haproxy.cfg
systemctl reload haproxy
echo "active backend=$port"
EOF
chmod 755 /usr/local/sbin/activate-vps-backend

# Only the control key may run the activation command.
# Paste the generated control public key after replacing PLACEHOLDER.
cat >/home/relay-control/.ssh/authorized_keys <<'EOF'
command="/usr/local/sbin/activate-vps-backend",no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty ssh-ed25519 PLACEHOLDER_CONTROL_PUBLIC_KEY
EOF
chown relay-control:relay-control /home/relay-control/.ssh/authorized_keys
chmod 600 /home/relay-control/.ssh/authorized_keys

cat >/etc/ssh/sshd_config.d/99-own-vps-relay.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowTcpForwarding remote
GatewayPorts no
PermitTunnel no
X11Forwarding no
EOF

systemctl enable --now ssh
systemctl enable --now haproxy
haproxy -c -f /etc/haproxy/haproxy.cfg
systemctl restart haproxy
systemctl restart ssh

echo "Relay base installation complete."
echo "Next: replace PLACEHOLDER_CONTROL_PUBLIC_KEY and add the tunnel public key to relay-tunnel authorized_keys."
echo "Public Termius endpoint: <relay-host>:2222"
