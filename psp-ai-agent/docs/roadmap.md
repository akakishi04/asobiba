# Roadmap and Design Gates

## 1. Status

Current status: **DESIGN ONLY**.

No implementation work is authorized by this document. The phases below describe a future implementation order and the evidence required before moving forward.

## 2. Strategy

The project should progress from observability to mutation, then from primitive control to AI integration.

Recommended order:

```text
Protocol semantics
    -> mock/test transport
    -> PSP connection + heartbeat
    -> framebuffer observation
    -> semantic observation
    -> bounded controller input
    -> verification loop
    -> MCP facade
    -> game adapters
```

MCP is deliberately late. The difficult part is establishing a reliable PSP control plane; wrapping an unstable device interface in MCP would only make failures harder to diagnose.

## 3. Phase D0 — Design freeze for the first prototype

### Decide

- session/generation semantics;
- capability identifiers;
- request/action ID semantics;
- input neutralization behavior;
- frame metadata;
- minimum semantic snapshot;
- reconnect behavior;
- error taxonomy;
- boundary between Bridge and MCP Server.

### Gate D0

Pass when the expected behavior for disconnect, reconnect, stale action, action acknowledgement, and missing capabilities can be described without referring to a specific source-code implementation.

## 4. Phase P0 — Protocol test fixture

Future implementation goal: build a PC-only fake PSP endpoint or replay fixture.

It should allow testing:

- connect/disconnect;
- protocol negotiation;
- session replacement;
- heartbeat;
- screenshots represented by fixture frames;
- action acknowledgement;
- timeout and duplicate-request cases.

### Gate P0

The bridge can be tested without a physical PSP.

This prevents every protocol/debug cycle from depending on hardware.

## 5. Phase P1 — Physical session and heartbeat

Future implementation scope:

- minimal PSP-side agent;
- one transport;
- protocol handshake;
- identity/capability report;
- heartbeat;
- clean disconnect/reconnect.

No controller injection is required yet.

### Gate P1

Repeated physical connect/disconnect cycles create correct new session generations and never reuse stale pending requests.

## 6. Phase P2 — Framebuffer observation

Future scope:

- obtain PSP framebuffer frames;
- transfer frame metadata;
- expose capture to the bridge;
- measure dropped frames and transfer latency;
- detect stale/frame-stalled conditions separately from disconnect.

Optimization is secondary to correctness.

### Gate P2

The PC can continuously establish what frame it received and whether frame progression is occurring. A dropped frame does not corrupt session state.

## 7. Phase P3 — Generic semantic observation

Future scope:

- runtime mode when reliable;
- title ID when reliable;
- PSP agent heartbeat/frame counters;
- CPU clock and free-memory summary if safe/stable;
- injected-input state placeholder;
- capability-gated optional fields.

### Gate P3

Semantic fields have documented provenance and unavailable fields remain explicitly unavailable instead of being guessed.

## 8. Phase P4 — Bounded controller injection

Future scope:

- digital button down/up;
- bounded press;
- analog control;
- neutralize operation;
- controller lease/watchdog;
- action IDs and acknowledgements.

### Gate P4

For cable loss, bridge crash simulation, timeout, and normal completion, injected controller state returns to neutral according to the documented contract.

No AI integration should precede this gate.

## 9. Phase P5 — Observe/act/verify harness

Future scope:

Build a deterministic PC test harness capable of scenarios such as:

```text
capture state
-> issue one bounded action
-> wait for observable change
-> capture resulting state
-> record trace
```

This is not yet an LLM feature.

### Gate P5

Failures can be classified as at least:

- vision/expected-state mismatch;
- device alive but application not progressing;
- action not applied;
- transport failure;
- session replacement;
- unsupported observation.

## 10. Phase P6 — MCP server

Only after the bridge contract is stable, expose the initial tools:

```text
psp.get_session
psp.observe
psp.screenshot
psp.press
psp.analog
psp.neutralize_input
psp.wait_for
```

### Gate P6

The MCP server contains no PSP-specific transport logic. Equivalent behavior can be exercised against the physical bridge and the protocol test fixture.

## 11. Phase P7 — AI pilot

Future experiments should begin with bounded tasks rather than unrestricted autonomous gameplay.

Suggested progression:

1. identify whether XMB or a game is active;
2. move between known XMB locations;
3. launch a known title;
4. detect successful launch;
5. navigate one controlled menu sequence;
6. recover from an intentionally introduced unexpected state.

### Gate P7

The AI demonstrates closed-loop behavior: it re-observes and changes its plan when expected state does not occur instead of continuing an open-loop macro.

## 12. Phase P8 — Optional game adapters

Only after generic control works.

Adapter work should be driven by a concrete game/use case.

Each adapter requires:

- title/version compatibility declaration;
- namespaced schema;
- explicit invalid/unavailable state;
- regression fixture where practical;
- no hard dependency from the generic bridge.

## 13. Phase P9 — CFW-specific extensions

ARK-specific integration is an optimization/extension phase, not the foundation.

Potential future uses include richer module/plugin diagnostics or more reliable platform state. Any such feature remains capability-gated behind a platform adapter.

A generic PSP feature should not be made ARK-specific merely because ARK is the first development environment.

## 14. Explicitly deferred decisions

The design intentionally does **not** yet choose:

- exact PSP SDK/CFW API hooks;
- exact RemoteJoy/PSPLINK code reuse strategy;
- transport wire encoding;
- image compression format;
- PC implementation language;
- MCP SDK/language;
- GUI framework;
- exact controller merge policy with physical input;
- supported PSP hardware models for prototype 1;
- first game adapter.

These are implementation decisions and should be made when their constraints are measurable.

## 15. First future implementation milestone

If implementation is later authorized, the recommended first milestone is **not MCP** and not AI gameplay.

It is:

```text
PC test program
    <->
minimal Bridge Protocol
    <->
PSP Agent

Capabilities:
- connect
- identify session
- heartbeat
- capture one framebuffer frame
- disconnect cleanly
```

That milestone validates the hardest architectural boundary while keeping mutation out of the first hardware test.

## 16. Success criterion for the project

The project succeeds when an agent can operate a real PSP through a stable, inspectable control plane where:

- every observation has provenance;
- every mutation is bounded and tracked;
- disconnect/reconnect is explicit;
- the agent can verify effects;
- game-specific knowledge is optional;
- AI/MCP concerns do not leak into PSP kernel/device code.

The measure is not how many buttons the AI can press. It is how reliably the system can determine and explain what happened.