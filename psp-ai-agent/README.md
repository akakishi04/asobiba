# PSP AI Agent

Design-only workspace for a PSP automation and observation platform that can be controlled by an AI through a PC-side MCP server.

> Status: **DESIGN ONLY**
>
> This directory intentionally contains no implementation, build scripts, binaries, firmware patches, or vendored dependencies yet.

## Goal

Create a generic interface that lets an AI observe and operate a real PSP without making the PSP itself responsible for LLM inference or MCP.

The target architecture is:

```text
LLM / Agent
    |
    | MCP
    v
PC-side PSP MCP Server
    |
    | typed internal API
    v
PC-side PSP Bridge
    |
    | USB first; transport is replaceable
    v
PSP-side Agent PRX
    |
    +-- controller input/output
    +-- framebuffer capture
    +-- system observation
    +-- heartbeat / watchdog state
    +-- optional game adapters
```

The system should combine two kinds of observation:

1. **Pixel observation** — what is actually visible on the PSP screen.
2. **Semantic observation** — machine-readable state exposed by the PSP-side agent.

Neither is authoritative on its own for every decision. Higher-level agents should be able to cross-check both.

## Design principles

- Keep the PSP-side component small and deterministic.
- Keep MCP, AI integration, image interpretation, history, policy, and orchestration on the PC.
- Separate **observation**, **decision**, **action**, and **verification**.
- Prefer semantic state over guessing when the PSP can expose the fact directly.
- Preserve framebuffer observation so the AI can still handle unknown games and menus.
- Treat every input as an explicit action with an observable result.
- Avoid open-loop button macros as the primary control model.
- Make transport replaceable; USB is the first target, not part of the semantic contract.
- Do not require ARK-specific behavior in the public protocol unless no portable alternative exists.
- ARK integration, if later needed, belongs behind a PSP platform adapter.
- No implementation starts until the observation/action contract is stable enough to test independently.

## Intended capability levels

### Level 0 — Connection and identity

The PC can detect the PSP-side agent, negotiate protocol version, identify the device/model, and receive a heartbeat.

### Level 1 — Generic observation and input

The PC can obtain screenshots/framebuffer frames, query generic runtime state, press/release buttons, and control the analog stick.

### Level 2 — Verified interaction

Actions carry IDs and acknowledgements. The PC can observe frame progression and determine whether the PSP is alive, stalled, disconnected, or simply loading.

### Level 3 — Semantic platform state

The agent can expose safe generic facts such as runtime mode, title ID when available, clock state, free memory, loaded plugin/module summary, and selected diagnostics.

### Level 4 — Optional game adapters

A game-specific adapter may expose structured game state, but it must not be required for generic operation. The generic vision/input path remains usable when no adapter exists.

## Non-goals for the first implementation

- Running an LLM on the PSP.
- Implementing an MCP server on the PSP.
- Autonomous firmware modification.
- Replacing ARK-5 or becoming a new CFW.
- Making arbitrary memory mutation the primary gameplay/control mechanism.
- Treating screenshot-only computer use as sufficient state estimation.
- Building game-specific automation before the generic transport and observation contract is validated.

## Documents

- [`docs/architecture.md`](docs/architecture.md) — component boundaries and data flow.
- [`docs/protocol-and-mcp.md`](docs/protocol-and-mcp.md) — PSP bridge protocol and MCP surface.
- [`docs/observation-and-control.md`](docs/observation-and-control.md) — observation model, action semantics, verification, and recovery.
- [`docs/roadmap.md`](docs/roadmap.md) — staged implementation gates for a future implementation.

## Core architectural decision

The project is **not** "AI sends PSP button presses".

It is an **observe -> decide -> act -> verify** control system in which the PSP exposes the minimum reliable machine state needed to prevent the AI from depending entirely on visual guesses.

That distinction is the main design requirement.