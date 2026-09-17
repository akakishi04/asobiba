# Protocol and MCP Contract

## 1. Purpose

This document defines the intended contract between:

1. the PSP-side agent and the PC bridge; and
2. the PC-side MCP server and an AI agent.

These are deliberately separate protocols.

```text
AI <---- MCP ----> MCP Server <---- typed API ----> Bridge <---- device protocol ----> PSP
```

The device protocol should optimize for deterministic machine communication.
The MCP surface should optimize for safe, understandable agent use.

## 2. Device protocol requirements

The initial device protocol should support:

- version negotiation;
- capability negotiation;
- request IDs;
- response IDs;
- asynchronous events;
- bounded payload lengths;
- explicit error codes;
- heartbeat/liveness;
- screenshot/frame payload transfer;
- action acknowledgement;
- session generation identity.

The exact binary encoding is intentionally undecided at this design stage.

### 2.1 Envelope model

Conceptually, every request/response should have fields equivalent to:

```text
protocol_version
session_generation
message_type
request_id
payload_length
payload
```

Responses additionally carry a normalized status.

### 2.2 Protocol versioning

Use major/minor semantics.

- Major mismatch: communication rejected unless an explicit compatibility path exists.
- Minor mismatch: negotiate the highest mutually supported feature set.
- Individual optional features are still capability-gated.

Do not infer support from version alone when a capability flag can state it explicitly.

## 3. Session model

A session describes one continuous PSP-agent connection.

Each connection has:

- `session_id` — opaque identifier;
- `generation` — increments whenever the bridge establishes a replacement connection;
- `protocol_version`;
- `capabilities`;
- `device_identity`;
- `connected_at`;
- `last_heartbeat`.

All observations and action results belong to one session generation.

If the device disconnects and reconnects, pending actions from the previous generation must not be replayed automatically.

## 4. Observation contract

### 4.1 Snapshot

A generic snapshot should be able to contain:

```json
{
  "session_generation": 4,
  "observation_seq": 1921,
  "runtime": {
    "mode": "GAME",
    "title_id": "optional",
    "frame_counter": 78219
  },
  "device": {
    "model": "optional",
    "cpu_clock_mhz": 333,
    "free_memory_bytes": 18350080
  },
  "input": {
    "injected_buttons": [],
    "analog_x": 0.0,
    "analog_y": 0.0
  }
}
```

Fields unsupported by the connected capability set should be absent or explicitly unavailable, not filled with guessed values.

### 4.2 Frame observation

A frame response should have metadata separate from image bytes.

Conceptually:

```text
session_generation
frame_id
psp_frame_counter
capture_timestamp/tick
width
height
pixel_format
encoding
payload
```

The AI-facing MCP tool may convert this into whatever image representation is supported by the client, but the bridge should retain the original frame metadata.

### 4.3 Coherency

A semantic snapshot and screenshot captured separately are not automatically the same instant.

Therefore the API should expose sequence/frame information so the caller can understand their temporal relationship.

A future compound observation may request:

```text
observe_bundle(frame = true, semantic = true)
```

where the PSP/bridge attempts to sample them as close together as practical and reports the actual identifiers.

## 5. Input contract

### 5.1 Primitive digital actions

Primitive operations:

```text
button_down(button)
button_up(button)
neutralize_input()
```

Convenience operation:

```text
press(button, duration_ms)
```

The bridge implements `press` in terms of bounded input state and guarantees cleanup when possible.

### 5.2 Analog action

The logical analog contract should use normalized values:

```text
x in [-1.0, 1.0]
y in [-1.0, 1.0]
```

The PSP adapter converts these into hardware/native ranges.

A bounded operation may be:

```text
set_analog(x, y, duration_ms)
```

After a bounded operation expires, injected analog state returns to neutral unless superseded by a newer action.

### 5.3 Action IDs

Every action gets an `action_id`.

Possible lifecycle:

```text
ACCEPTED
APPLIED
COMPLETED
REJECTED
TIMED_OUT
CANCELLED
SESSION_LOST
```

`ACCEPTED` only means the bridge accepted the request.
It must not be presented to the AI as proof that the PSP executed it.

## 6. Initial MCP surface

The MCP surface should begin small.

### `psp.get_session`

Returns:

- connection state;
- session generation;
- device identity;
- protocol version;
- capabilities.

No mutation.

### `psp.observe`

Returns a generic semantic snapshot.

Arguments may later allow selected groups, but version 0 should prefer a stable bounded snapshot over arbitrary field querying.

### `psp.screenshot`

Returns the most recent or newly captured framebuffer image with frame metadata.

### `psp.press`

Arguments:

```text
button
duration_ms (bounded)
```

Returns action ID and application/completion status.

### `psp.analog`

Arguments:

```text
x
y
duration_ms (bounded)
```

Returns action ID and status.

### `psp.neutralize_input`

Immediately requests release/neutralization of all AI-injected controller state.

This should remain a first-class tool rather than an implementation detail.

### `psp.wait_for`

A PC-side convenience tool.

It may wait for bounded conditions such as:

- frame counter changes;
- runtime mode changes;
- title ID changes;
- connection loss;
- semantic predicate supported by the server.

It must always have a bounded timeout.

This avoids making the LLM perform tight polling loops.

## 7. Tools intentionally deferred

The following should not be in the first MCP version:

- arbitrary PSP memory read/write;
- arbitrary kernel calls;
- module injection;
- firmware modification;
- shell-like unrestricted command execution;
- game-specific tools in the generic namespace;
- autonomous macro recording/playback without verification.

They either expand the trust boundary too much or couple the generic interface to implementation details before the observation/control model is proven.

## 8. Game adapter namespace

Game-specific capabilities should be exposed under a separate namespace or dynamic resource description.

Example concept:

```text
psp_game.observe
psp_game.capabilities
```

with adapter identity returned as data:

```json
{
  "adapter_id": "example-game-v1",
  "title_id": "...",
  "schema_version": 1
}
```

The generic MCP server must remain usable when this namespace is unavailable.

## 9. Error model

MCP-visible errors should be normalized and actionable.

Examples:

```text
NOT_CONNECTED
SESSION_CHANGED
UNSUPPORTED
INVALID_ARGUMENT
ACTION_REJECTED
ACTION_TIMEOUT
FRAME_UNAVAILABLE
FRAME_STALLED
DEVICE_UNRESPONSIVE
ADAPTER_UNAVAILABLE
INTERNAL_BRIDGE_ERROR
```

Each error should distinguish whether retry is sensible.

Conceptually:

```json
{
  "code": "SESSION_CHANGED",
  "retryable": true,
  "details": {
    "expected_generation": 3,
    "current_generation": 4
  }
}
```

## 10. Idempotency and replay

Observation calls are naturally repeatable.

Input calls are not automatically idempotent.

Therefore:

- action IDs are unique within a bridge session;
- an action must never be silently replayed after reconnect;
- retrying an MCP mutation should create a deliberate new action unless the bridge can prove the previous request was never applied;
- the bridge may retain a bounded recent-action ledger to answer duplicate request IDs consistently.

## 11. Timeouts

All operations that wait must be bounded.

Timeout layers should be distinct:

- transport timeout;
- PSP response timeout;
- action completion timeout;
- semantic wait timeout.

A timeout is not proof of non-execution. Results should preserve uncertainty when acknowledgement was lost.

## 12. First protocol design gate

Before implementation begins, the following must be fixed enough to write protocol conformance tests:

1. session/generation semantics;
2. message envelope fields;
3. capability negotiation;
4. action acknowledgement semantics;
5. frame metadata;
6. normalized error categories;
7. disconnect/reconnect behavior;
8. input neutralization guarantee.

Binary serialization choice can remain open until these semantics are stable.