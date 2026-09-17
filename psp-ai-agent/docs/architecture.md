# Architecture

## 1. Scope

This document defines the proposed architecture for a generic PSP observation and control platform intended to be consumed by AI agents through a PC-side MCP server.

This is a design document only. It does not select final libraries, USB drivers, firmware hooks, or implementation language beyond what is necessary to define boundaries.

## 2. Architectural shape

```text
+-------------------------------------------------------+
| Agent / LLM                                           |
| - planning                                            |
| - visual interpretation                              |
| - task policy                                         |
+-----------------------------+-------------------------+
                              |
                              | MCP
                              v
+-------------------------------------------------------+
| PC MCP Server                                         |
| - stable tool schema                                  |
| - validation                                          |
| - capability discovery                                |
| - converts agent calls into bridge requests           |
+-----------------------------+-------------------------+
                              |
                              | typed internal API
                              v
+-------------------------------------------------------+
| PC Bridge                                             |
| - transport session                                   |
| - request IDs / timeouts                              |
| - frame decoding                                      |
| - reconnect logic                                     |
| - event stream                                        |
| - logging                                             |
+-----------------------------+-------------------------+
                              |
                              | transport adapter
                              v
+-------------------------------------------------------+
| PSP Agent PRX                                         |
| - protocol endpoint                                   |
| - framebuffer provider                                |
| - input provider                                      |
| - semantic state providers                            |
| - heartbeat                                           |
| - optional platform/game adapters                     |
+-----------------------------+-------------------------+
                              |
                              v
+-------------------------------------------------------+
| PSP runtime / CFW / game / XMB                        |
+-------------------------------------------------------+
```

## 3. Responsibility boundaries

### 3.1 Agent / LLM

The LLM may:

- interpret screenshots;
- choose goals and actions;
- reason over semantic observations;
- detect inconsistencies between visual and structured state;
- decide when additional observation is required.

The LLM should not:

- own the low-level USB session;
- assume that a tool call means the physical input occurred;
- infer transport health from UI appearance alone;
- depend on implementation-specific PSP memory addresses.

### 3.2 MCP server

The MCP server is a stable AI-facing facade.

It owns:

- tool names and schemas;
- argument validation;
- capability discovery;
- high-level error normalization;
- optional convenience operations built from primitive bridge operations.

It does not directly know PSP kernel internals. Those belong below the bridge boundary.

### 3.3 PC bridge

The bridge owns the live device session.

It is responsible for:

- connection lifecycle;
- protocol negotiation;
- sequencing;
- request/response correlation;
- event delivery;
- action acknowledgement;
- deadlines and cancellation;
- frame transfer/reassembly;
- reconnect behavior;
- durable diagnostic logs.

The bridge should expose a typed API that could later be consumed by something other than MCP, for example a desktop diagnostics UI or test harness.

This separation prevents the MCP protocol from becoming the device protocol.

### 3.4 PSP Agent PRX

The PSP-side agent should be intentionally small.

It owns:

- reading generic device/runtime state;
- capturing or exposing framebuffer data;
- injecting controller state through a controlled input provider;
- maintaining heartbeat and frame counters;
- reporting capability availability;
- exposing optional providers for platform-specific facts.

It should avoid:

- AI logic;
- long-lived task planning;
- complex configuration parsing;
- internet APIs;
- package management;
- large caches;
- arbitrary plugin discovery logic unless needed for diagnostics.

## 4. Core interfaces

The architecture is organized around five logical interfaces.

### 4.1 Session

Represents the physical/logical connection.

Minimum concepts:

- protocol version;
- device session ID;
- PSP model/capability profile;
- uptime / heartbeat counter;
- transport state;
- reconnect generation.

A reconnect creates a new session generation. An agent must not silently assume that observations from the previous generation still describe current state.

### 4.2 Observation

Observation is split into:

- visual observation;
- platform semantic observation;
- diagnostics;
- optional game-specific observation.

Every observation should carry enough metadata to establish when it was sampled, including at minimum:

- session generation;
- observation sequence;
- PSP-side monotonic tick or counter where feasible;
- framebuffer frame counter where relevant.

### 4.3 Action

Controller action is the first generic mutation surface.

Primitive actions should cover:

- button down;
- button up;
- bounded press;
- analog state;
- neutralize all injected input.

A high-level `press(CROSS)` is a convenience operation over explicit down/up semantics.

Every mutation receives an action ID and explicit result.

### 4.4 Event

The PSP/bridge may emit events independently of MCP polling.

Examples:

- connected;
- disconnected;
- heartbeat missed;
- runtime mode changed;
- title changed;
- frame stalled;
- action applied;
- PSP-side agent fault;
- capability changed.

The first version need not expose all events directly through MCP, but the bridge architecture should not preclude them.

### 4.5 Capability

Features are negotiated, not assumed.

Example capability identifiers:

```text
observation.framebuffer
observation.runtime_mode
observation.title_id
observation.memory_summary
observation.module_summary
control.digital_buttons
control.analog
control.input_neutralize
diagnostics.heartbeat
diagnostics.frame_counter
adapter.game_state
```

This lets older PSP-side agents coexist with newer PC software.

## 5. Transport design

USB is the first intended transport because it offers low latency and does not require modern networking support on the PSP.

However, transport must sit below the logical protocol.

```text
Bridge Protocol
    |
    +-- USB transport (first target)
    +-- WLAN transport (possible future target)
    +-- emulator/test transport (recommended for tests)
```

The protocol must not encode assumptions such as USB endpoint numbers into MCP-visible semantics.

## 6. Pixel + semantic observation

The system deliberately keeps both observation paths.

### Pixel path

Useful for:

- unknown games;
- arbitrary menus;
- text and visual state;
- validating what the user would actually see.

Weaknesses:

- ambiguous menus;
- loading vs freeze ambiguity;
- hidden state;
- visual effects and transitions;
- OCR/vision failure.

### Semantic path

Useful for:

- exact runtime mode;
- title identity;
- liveness;
- memory/clock diagnostics;
- transport-independent state confirmation.

Weaknesses:

- only facts explicitly instrumented can be observed;
- game-specific semantics require adapters;
- hooks may vary by environment.

The recommended policy is not "semantic always wins". Each field must define its authority. For example, title ID can be semantic-authoritative while menu selection may only be visually observable.

## 7. Platform abstraction

The public architecture must not make ARK-5 the protocol.

Instead:

```text
PSP Agent Core
    |
    +-- Generic PSP providers
    |
    +-- CFW platform adapter
          |
          +-- ARK adapter (candidate)
```

If an observation can be implemented generically, it belongs in the generic provider. CFW-specific APIs are used only behind an adapter.

This allows experimentation with ARK while keeping the project conceptually independent from a particular CFW.

## 8. Game adapters

Game adapters are optional extensions.

They may expose structured observations such as:

- player state;
- world state;
- current menu/state machine;
- selected target;
- domain-specific counters.

Rules:

1. The generic agent remains functional without them.
2. Adapter failure must not break generic framebuffer/input control.
3. Adapter data is namespaced.
4. Adapter compatibility includes title/version identity.
5. An adapter must report unavailable rather than returning fabricated defaults.

## 9. Failure domains

Failures should be distinguishable rather than collapsed into "PSP did not respond".

Minimum categories:

- `TRANSPORT_DISCONNECTED`
- `SESSION_REPLACED`
- `REQUEST_TIMEOUT`
- `UNSUPPORTED_CAPABILITY`
- `INVALID_ACTION`
- `ACTION_NOT_APPLIED`
- `FRAME_UNAVAILABLE`
- `FRAME_STALLED`
- `PSP_AGENT_FAULT`
- `ADAPTER_UNAVAILABLE`
- `ADAPTER_INCOMPATIBLE`

This is important for an AI agent because different errors imply different recovery behavior.

## 10. Security and control boundary

The first version should default to a local, explicitly connected device.

Principles:

- no public network listener by default;
- one controlling bridge session at a time;
- PSP-side input injection can always be neutralized;
- disconnect releases injected inputs;
- capability negotiation prevents accidental unsupported operations;
- dangerous future capabilities must be opt-in rather than silently added to generic control.

## 11. Key design decision

The architecture should optimize for **observability before autonomy**.

A highly capable AI cannot reliably control a device it cannot diagnose. Therefore framebuffer capture, heartbeat, frame progression, explicit action acknowledgement, and session identity are foundational features rather than optional debugging additions.