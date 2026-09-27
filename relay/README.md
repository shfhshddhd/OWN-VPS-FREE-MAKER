# Fixed SSH Relay

This is the independent public TCP/SSH relay for the rolling GitHub-hosted worker.

```
Termius
   |
   v
RELAY_HOST:2222
   |
   v
HAProxy TCP
   |
   v
127.0.0.1:<active tunnel>
   |
   v
current GitHub runner:22
```

## Why a relay is required

A GitHub-hosted runner gets a temporary public network identity. A GitHub Secret cannot create or reserve an arbitrary public IP. The relay is therefore the stable public endpoint while workers rotate.

## Setup

Use any persistent Linux host that you control and that provides a real public IPv4/IPv6 address.

1. Run `relay/setup-relay.sh` as root.
2. Generate a tunnel key pair and a separate control key pair.
3. Put the tunnel public key in `relay-tunnel` authorized_keys.
4. Put the control public key in the restricted `relay-control` authorized_keys entry.
5. Allow inbound TCP/2222.
6. Keep TCP/22 available only for relay administration.
7. Configure the GitHub secrets listed below.

### GitHub secrets

```
RELAY_HOST
RELAY_USER
RELAY_TUNNEL_PRIVATE_KEY
RELAY_CONTROL_PRIVATE_KEY
VPS_STATE_KEY
SSH_AUTHORIZED_KEYS
```

`SSH_AUTHORIZED_KEYS` can contain multiple public keys, one per line. This is how you can give yourself and a friend separate SSH keys while both use the same Termius Host + Port.

## Termius

Use:

- Host: relay public DNS name or fixed IP
- Port: `2222`
- Username: `root`
- Identity: your own SSH private key

A friend uses the same Host, Port and username, but their own private key. Their public key must be present in `SSH_AUTHORIZED_KEYS`.

## Handover behavior

The workflow starts the replacement runner before releasing the old worker. The relay switches new TCP connections to the replacement.

Existing SSH/TCP sessions are not live-migrated. A session already attached to the old GitHub VM can drop during rotation and must reconnect.

Files/RAM are also different:

- `/opt/vps-data` and PM2 state are snapshotted
- RAM, running processes and open TCP sockets cannot be migrated
- SSH host keys are not restored onto the replacement

## Security

Never commit private keys or `VPS_STATE_KEY`.

The tunnel key is restricted to remote forwarding. The control key is restricted to the activation command.
