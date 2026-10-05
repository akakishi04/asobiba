# Minecraft Data Logger

Structured telemetry for LLM / agent training and debugging.

## v0.1

Each player login creates a session directory:

```text
minecraft-data-logger/
  20261005-171500_<uuid>/
    metadata.json
    observations.jsonl
    events.jsonl
```

Observation records contain:

- schema version
- session id
- sequence id
- server game tick
- position and velocity
- yaw / pitch
- health and hunger
- dimension
- on-ground state
- main-hand item
- optional compact inventory snapshot

Event records currently cover:

- login
- logout
- block break
- entity death / player kill

Writes go through a bounded background JSONL writer so normal server ticks do not synchronously flush every record.

## Important design rule

The logger observes gameplay and does not alter gameplay. Dataset transformations (SFT pairs, action prediction windows, reward labels, etc.) should be downstream tooling, not baked into the capture format.

## Planned

- explicit `observation_before -> action -> result -> observation_after` linkage
- client frame capture (OFF / interval / action-boundary)
- server-side ray/crosshair target snapshot
- nearby entity summary
- schema migration/version validation
- session manifest with mod list and hashes
