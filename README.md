# OWN VPS FREE MAKER

Tailscale-free rolling SSH VPS architecture using GitHub Actions workers and one persistent SSH relay.

## Architecture

```
Termius
   |
   v
Fixed relay host:2222
   |
   v
HAProxy TCP
   |
   +--> current reverse SSH tunnel
             |
             v
       current GitHub runner
       A -> B -> C -> D...
```

GitHub-hosted runners are disposable. The runner public IP is therefore never used as the client endpoint.

The persistent relay keeps the same Termius Host + Port while the active backend changes.

## Current workflow

`.github/workflows/vps.yml`

The worker:

1. boots a fresh Ubuntu runner
2. restores encrypted application state when this is a handover
3. creates an outbound reverse SSH tunnel to the relay
4. verifies the worker SSH service
5. activates its tunnel on the relay
6. publishes a READY artifact for the previous worker
7. snapshots persistent files with AES-256 GPG encryption
8. dispatches the next worker
9. waits for the next worker to become READY
10. finishes the old worker

The workflow uses `workflow_dispatch` chaining. GitHub documents that `workflow_dispatch` events can create workflow runs when initiated with `GITHUB_TOKEN`, subject to repository permissions. 

## Relay

See:

- `relay/setup-relay.sh`
- `relay/README.md`

The relay is an independent Linux VM. HAProxy runs in TCP mode and forwards SSH connections to the active loopback reverse tunnel.

Public endpoint:

`RELAY_HOST:2222`

Termius should use:

- Host: your relay DNS name or fixed IP
- Port: `2222`
- Username: `root` on the GitHub worker
- Authentication: your normal SSH private key

## Required GitHub Actions secrets

```
RELAY_HOST
RELAY_USER
RELAY_TUNNEL_PRIVATE_KEY
RELAY_CONTROL_PRIVATE_KEY
VPS_STATE_KEY
SSH_AUTHORIZED_KEYS
```

Never commit private keys or `VPS_STATE_KEY` to the repository.

## State limitations

This is rolling replacement, not live VM migration.

Files included in the snapshot are:

- `/opt/vps-data`
- `/root/.pm2`
- `/root/.ssh/authorized_keys`
- SSH host keys are captured for archival but deliberately not restored onto a new worker

RAM, open processes, open TCP sockets, and existing SSH sessions cannot be migrated between GitHub-hosted VMs. A client may therefore need to reconnect during a worker rotation.

For applications that write important data elsewhere, add those paths to the encrypted snapshot before relying on them across handovers.

## Free relay option

Oracle Cloud documents Always Free compute resources, including free VM resources in the tenancy's home region. Capacity can vary by region, so availability is not guaranteed at instance creation time.

No Tailscale is used by this project.
