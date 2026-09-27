# OWN-VPS-FREE-MAKER

This repository builds an experimental rolling VPS-style worker on GitHub-hosted Ubuntu runners.

## Current architecture

GitHub-hosted runners are temporary VMs. GitHub documents that public repositories currently receive standard Ubuntu runners with 4 CPU and 16 GB RAM, and that each job runs on a fresh VM. GitHub-hosted jobs have a 6-hour execution limit.

This project therefore treats every runner as a disposable worker:

A → B → C → D → ...

Before the current worker reaches the limit, it:

1. Saves an encrypted VPS snapshot
2. Uploads the snapshot as a protected-by-encryption artifact
3. Dispatches the next workflow using `workflow_dispatch`
4. The next worker restores the application/filesystem state
5. The next worker reports READY
6. The old worker publishes a RELEASE signal
7. The replacement may then restore the persistent network identity and take over

GitHub confirms that `workflow_dispatch` can be triggered from a workflow using `GITHUB_TOKEN`, and that this exception creates a new workflow run.

## Network

The management network uses Tailscale.

Tailscale assigns a stable IP to a registered node. The IP remains stable while that node remains registered; losing the node state causes a new identity/IP.

The workflow deliberately does **not** clone the Tailscale node state while the old worker is still active. Tailscale documents that cloning node state can create duplicate node identities/IPs.

The intended handover is:

OLD ACTIVE
→ NEW PREPARED
→ NEW READY
→ OLD RELEASE
→ NEW RESTORES PERSISTENT IDENTITY
→ NEW ACTIVE

## Required secrets

Add these repository Actions secrets:

### TAILSCALE_AUTHKEY

A Tailscale auth key that allows the temporary worker to join your tailnet.

### VPS_STATE_KEY

A long random passphrase used to encrypt the VPS snapshot.

Because the repository is public, never upload the snapshot unencrypted.

### SSH_AUTHORIZED_KEYS

One or more SSH public keys, one per line.

Never put private SSH keys in this secret or in the repository.

## First run

1. Add all three secrets
2. Open Actions
3. Select **OWN VPS - Rolling 24/7 Worker**
4. Choose **initial**
5. Run it
6. The logs will show the temporary Tailscale IP
7. Connect from Termius using SSH on port 22 and the private key corresponding to your authorized public key

For your friend, use a separate SSH public key and authorize that key as well. The friend also needs access to the same Tailscale network.

## Persistent VPS data

For applications that must survive worker replacement, use:

`/opt/vps-data`

The workflow persists:

- /opt/vps-data
- PM2 state
- root authorized SSH keys
- SSH host keys
- Tailscale node state

The snapshot is encrypted with `VPS_STATE_KEY` before it is uploaded.

GitHub artifacts are designed to persist files between workflow runs and can be downloaded by a later run with the appropriate token/run ID.

## Important limitation

This is **not literal VM live migration**.

A GitHub-hosted runner cannot have its live RAM, kernel state, open TCP sockets, or arbitrary process memory transferred to another GitHub VM.

The design provides rolling worker replacement and persistent filesystem/application state. Applications such as Telegram bots may still need to reconnect after the worker handover.

A true permanent production VPS should use a persistent VM/cloud server or a self-hosted runner. GitHub-hosted runners are intentionally disposable.
