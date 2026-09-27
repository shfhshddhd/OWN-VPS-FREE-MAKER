# Fixed SSH Relay

This relay is the permanent public endpoint for the rolling GitHub worker.

Architecture:

Termius -> relay-host:2222 -> HAProxy -> 127.0.0.1:<active tunnel> -> current GitHub runner:22

GitHub runners create outbound reverse SSH tunnels, so the runner's changing public IP never becomes the client endpoint.

## Setup

Use a persistent Linux VM. Oracle Cloud documents Always Free compute resources, including VM instances, but availability can vary by region.

1. Run `relay/setup-relay.sh` as root.
2. Generate two SSH key pairs:
   - tunnel key: used only by GitHub runners
   - control key: used only to activate a backend
3. Put the tunnel public key into:
   `/home/relay-tunnel/.ssh/authorized_keys`
4. Put the control public key into the restricted `relay-control` authorized_keys line.
5. Replace `PLACEHOLDER_CONTROL_PUBLIC_KEY` in the setup script before running it, or edit the authorized_keys file directly.
6. Allow inbound TCP/2222 in the VM firewall/security list.
7. Keep TCP/22 available for your own relay administration.
8. In GitHub Actions secrets set:
   - RELAY_HOST = relay DNS name or fixed public IP
   - RELAY_USER = relay-tunnel
   - RELAY_TUNNEL_PRIVATE_KEY = tunnel private key
   - RELAY_CONTROL_PRIVATE_KEY = control private key
   - VPS_STATE_KEY = random encryption passphrase
   - SSH_AUTHORIZED_KEYS = your normal SSH public key(s)

## Important

The relay does not migrate existing SSH/TCP sessions. HAProxy switches new connections to the new worker. Existing connections can still drop when GitHub destroys the old VM.

The state snapshot protects files and PM2 state, but it is not a live RAM migration. Applications that write outside /opt/vps-data or /root/.pm2 need their data added to the snapshot.

Do not put any private key into this repository.
