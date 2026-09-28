# OWN VPS FREE MAKER

A VPS-like 24/7 service built from disposable GitHub-hosted workers.

## Architecture

Controller -> Active worker -> Hot standby -> verified takeover -> next standby -> repeat.

Layers:
- GitHub Actions: disposable Ubuntu workers
- Docker: reproducible application layer
- MongoDB + GridFS: durable dynamic state and managed files
- SuperDMZ TCP relay: stable public Host:Port
- Controller/watchdog: reconciliation and crash recovery
- Password SSH: Termius access as root

Worker state:
CREATED -> BOOTSTRAPPING -> RESTORING -> STANDBY -> VERIFYING -> READY -> ACTIVE -> RETIRING -> CANCELLED
Failure path: FAILED -> RECOVERY

## Required GitHub secrets

- SUPERDMZ_TOKEN
- SSH_PASSWORD
- MONGODB_URI (or MONGO_URI)
- VPS_STATE_KEY

Do not commit secrets.

## Termius

Host: sareeffucker.dmzgate.com
Port: 16740
Username: root
Password: value of SSH_PASSWORD

## Important behavior

A standby is prepared without claiming the public relay. After Mongo verification and health checks, it acquires leadership, connects the relay, becomes ACTIVE, and only then the previous worker is cancelled.

The system preserves application state/files that are managed by the Mongo sync layer. It does not live-migrate RAM, kernel state, or existing TCP/SSH sockets.

GitHub-hosted jobs are disposable and subject to GitHub's execution limits, so continuity is provided by overlapping workers and durable state rather than by keeping one VM alive forever.
