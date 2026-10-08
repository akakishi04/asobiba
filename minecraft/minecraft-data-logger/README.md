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

## Optional server-side spatial context

Enable `logger.captureSpatialContext` to add to each observation:

- `crosshair_target`: nearest non-occluded entity or solid-block hit within 6 blocks, or `miss` / `unloaded`; includes identity, position and distance for valid hits
- `nearby_entities`: closest 16 living entities within 12 blocks, with entity type, UUID, world position, health and distance
- `nearby_entity_count` and `nearby_entities_truncated` identify omitted neighbors

The ray refuses to access unloaded chunks. Spatial capture is **OFF by default** because repeated world queries can add overhead in dense areas. This is server-authoritative observation data, not the local client's rendered pixel frame.

## Planned

- explicit `observation_before -> action -> result -> observation_after` linkage
- client frame capture (OFF / interval / action-boundary)
- schema migration/version validation
- session manifest with mod list and hashes
