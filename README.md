# OWN VPS FREE MAKER

Rolling SSH VPS architecture using GitHub-hosted workers and an independent fixed TCP relay.

## Architecture

```
Termius
   |
   v
FIXED RELAY_HOST:2222
   |
   v
HAProxy TCP
   |
   v
current reverse SSH tunnel
   |
   v
GitHub runner A -> B -> C -> D...
```

The GitHub runner is temporary. The relay is the stable public endpoint.

## Important

A GitHub Secret cannot reserve an arbitrary public IP. The Internet must have an actual machine/service that owns the public endpoint. This project uses that independent relay for exactly that reason.

A literal live migration of RAM, open TCP sockets, or an existing SSH session between GitHub VMs is not possible. The project instead performs rolling replacement: the new worker becomes ready, the relay switches new connections, and the old worker drains.

## Workflow

`.github/workflows/vps.yml`:

1. Boot a fresh Ubuntu runner
2. Restore encrypted application state
3. Start SSH
4. Open an outbound reverse SSH tunnel to the relay
5. Activate the worker on the fixed relay
6. Publish READY
7. Snapshot persistent state with AES-256 GPG encryption
8. Dispatch the next worker
9. Wait for the next worker READY
10. Drain the old worker

## Multi-user SSH

Set `SSH_AUTHORIZED_KEYS` to multiple public keys, one per line.

Each person keeps their own private key. Everyone can use the same Termius Host + Port while the server authenticates each person with their separate key.

## Relay setup

See `relay/setup-relay.sh` and `relay/README.md`.

The relay must be a real persistent Linux host with a public endpoint. No random IP in GitHub Secrets can replace it.

## Secrets

```
RELAY_HOST
RELAY_USER
RELAY_TUNNEL_PRIVATE_KEY
RELAY_CONTROL_PRIVATE_KEY
VPS_STATE_KEY
SSH_AUTHORIZED_KEYS
```

Never commit private keys or encryption secrets.
