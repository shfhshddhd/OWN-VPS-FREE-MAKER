# Relay layer

SuperDMZ provides the stable public TCP endpoint used by Termius.

Important:
- A standby worker does not connect the public relay until it passes restore/verification.
- This avoids two workers simultaneously claiming the same public endpoint.
- Existing SSH TCP sessions cannot be migrated between GitHub VMs; users may need to reconnect after a worker takeover.
