# OWN-VPS-FREE-MAKER

A rolling VPS-style environment built on GitHub-hosted Ubuntu runners.

## Architecture

```
Termius
   |
   | fixed host + port
   v
Tailscale Funnel
   |
   v
Current GitHub runner
   |
   +--> A -> B -> C -> D -> ...
```

The runner is disposable. The public SSH endpoint is not tied to the runner's temporary public IP.

GitHub documents that standard Linux runners in public repositories are fresh VMs with 4 CPU, 16 GB RAM and 14 GB SSD. GitHub-hosted jobs have a maximum execution time of 360 minutes, so this project performs a controlled handover before the limit.

## Stable SSH endpoint

The workflow uses Tailscale Funnel as the public TCP entry point.

SSH is forwarded through Funnel from:

```
own-vps.<your-tailnet>.ts.net:10000
```

Port 10000 is used because Tailscale Funnel supports raw TCP forwarding on 443, 8443 and 10000. Funnel provides a predictable DNS name for a device, so the hostname can be shared once and reused when the Funnel is turned back on.

Termius does not need Tailscale installed for the public Funnel endpoint.

## Handover sequence

1. Worker A starts and exposes the stable SSH Funnel.
2. A saves an encrypted application snapshot.
3. A starts Worker B.
4. B joins Tailscale using a temporary staging identity.
5. B restores application/filesystem state without cloning the live Tailscale identity.
6. B reports READY.
7. A releases the persistent Tailscale identity.
8. B restores the persistent Tailscale node state.
9. B enables the same Funnel endpoint.
10. B restores PM2 state and becomes the active worker.
11. B later repeats the same process for C.

The persistent Tailscale state is never cloned while A is still active. This avoids duplicate node identity problems.

## Required secrets

Create these repository Actions secrets:

### TAILSCALE_AUTHKEY

Tailscale auth key used by workers to join the tailnet.

### VPS_STATE_KEY

A long random passphrase used to encrypt the worker snapshot with AES-256.

### SSH_AUTHORIZED_KEYS

SSH public key or multiple public keys, one per line.

Never put a private SSH key in the repository or in this secret.

## Tailscale Funnel prerequisite

Funnel must be enabled for the tailnet before the workflow can expose the public SSH endpoint. Tailscale requires Funnel to be permitted by the tailnet policy.

After the first successful run, the workflow prints the Funnel endpoint in the Actions log.

## Termius

Use:

```
Host: own-vps.<your-tailnet>.ts.net
Port: 10000
Username: root
Authentication: SSH private key
```

Use separate SSH keys for different people when possible.

## Persistent state

The workflow currently persists:

- `/opt/vps-data`
- PM2 state
- SSH authorized keys
- SSH host keys
- persistent Tailscale node state

The snapshot is encrypted before upload.

GitHub Actions artifacts can be passed between workflow runs when the appropriate token and source run ID are supplied.

## Important limitations

This is rolling worker replacement, not literal VM live migration.

GitHub does not transfer live RAM, kernel state or open TCP sockets from A to B. An existing SSH session can therefore require reconnecting during a handover.

Applications that persist their important state to `/opt/vps-data` or have a reliable restart mechanism are the intended workload.

GitHub-hosted runners are disposable infrastructure. This project is designed as a free experimental VPS-style environment, not as a replacement for a permanent production VM.

## Current workflow

`.github/workflows/vps.yml`


<!-- relay architecture update pending -->
