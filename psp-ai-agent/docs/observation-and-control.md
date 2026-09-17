# Observation and Control Semantics

## 1. Why this document exists

The hardest part of AI device control is not generating button presses. It is knowing what state the device is actually in and whether an action had the intended effect.

This design therefore treats observation and verification as first-class subsystems.

## 2. Control loop

The default control loop is:

```text
OBSERVE
   |
   v
ESTIMATE STATE
   |
   v
CHOOSE ACTION
   |
   v
APPLY BOUNDED ACTION
   |
   v
VERIFY EFFECT
   |
   +---- success ----> next goal/action
   |
   +---- uncertain ---> observe again
   |
   +---- failure -----> recover / neutralize / stop
```

No high-level agent should assume success merely because an action request returned without a transport error.

## 3. Observation classes

### 3.1 Visual observation

Source: framebuffer capture.

Can answer questions such as:

- what menu is visible;
- what text/icon is on screen;
- where a cursor appears to be;
- whether a game visibly changed scene;
- whether animation continues.

It cannot reliably answer every hidden runtime fact.

### 3.2 Generic semantic observation

Source: PSP-side providers.

Candidate fields:

- runtime mode (`VSH`, `GAME`, `POPS`, `UNKNOWN`);
- title ID when reliably available;
- framebuffer/frame progression counter;
- monotonic heartbeat counter;
- CPU clock;
- free memory summary;
- currently injected input state;
- agent health;
- optional loaded-module/plugin summary.

Only fields that can be sampled with acceptable stability belong here.

### 3.3 Transport/bridge observation

Source: PC bridge.

Fields include:

- connected/disconnected;
- current session generation;
- request latency;
- most recent heartbeat age;
- dropped frame count;
- last successful PSP response;
- action ledger state.

This information must not be confused with PSP runtime state.

### 3.4 Game adapter observation

Optional and title-specific.

It may expose more useful semantics but is inherently less portable.

Adapter state should identify:

- adapter version;
- compatible title/version;
- sample sequence;
- validity status.

## 4. State confidence

The first implementation should avoid pretending to have a universal probabilistic confidence model.

Instead, observations should carry provenance and freshness. Higher-level software can derive confidence from facts such as:

- screenshot frame age;
- semantic sample sequence;
- heartbeat age;
- adapter validity;
- session generation match;
- whether frame progression continues.

The architecture should make uncertainty visible rather than hiding it behind one boolean `ready` flag.

## 5. Liveness vs progress

These are different concepts.

### Liveness

The PSP-side agent is still responding.

Evidence:

- heartbeat advances;
- protocol requests complete.

### Frame progress

The displayed framebuffer is changing or presenting new frames.

Evidence:

- PSP frame counter advances;
- captured frame IDs advance;
- optionally frame content changes.

### Application progress

The game/XMB meaningfully advanced toward the requested state.

This may require:

- semantic mode/title change;
- visual interpretation;
- game adapter state.

A loading screen can be alive with little visible change. A frozen game can leave the PSP-side agent alive. Therefore these signals must remain separate.

## 6. Action semantics

### 6.1 Bounded by default

AI-generated input should default to bounded actions.

Examples:

```text
press(CROSS, 80 ms)
analog(0.75, 0.0, 300 ms)
```

Unbounded `button_down` exists as a primitive but should be used sparingly by higher-level agents.

### 6.2 Neutral is a safety state

The system maintains a known neutral injected-controller state.

Neutralization should occur on:

- explicit `neutralize_input`;
- bounded action expiry;
- bridge session teardown when communication still permits cleanup;
- PSP-side watchdog expiry if the controller lease is not renewed.

A lost PC connection must not intentionally leave a button held forever.

### 6.3 Controller lease

Recommended future mechanism:

When AI injection is active, the PSP-side agent maintains a short-lived controller lease.

The bridge renews the lease while a bounded input is legitimately active.
If the lease expires, injected state becomes neutral.

This protects against:

- PC crash;
- cable loss;
- bridge crash;
- abandoned action sequence.

The exact lease duration is implementation-defined and should not leak into MCP semantics.

## 7. Verification patterns

### Pattern A — Visual menu action

```text
observe screenshot
-> identify current selection
-> press DOWN
-> wait for at least one new frame
-> capture screenshot
-> confirm selection changed visually
```

### Pattern B — Launch transition

```text
observe runtime mode/title
-> press CROSS
-> wait for runtime mode or title change with timeout
-> verify screenshot + semantic state
```

### Pattern C — Unknown action outcome

```text
send action
-> acknowledgement lost
-> DO NOT blindly repeat
-> inspect action ledger/session
-> observe current state
-> decide whether retry is safe
```

## 8. Stale observation protection

Every action decision should be traceable to a session generation and reasonably fresh observation.

A future high-level API may accept an optional precondition:

```text
expected_session_generation = 5
expected_observation_seq >= 120
```

If the session changed, the bridge rejects the action instead of executing a decision based on stale state.

This is especially important after reconnect.

## 9. Manual user input coexistence

The architecture should not assume the AI is the only source of controller state.

Possible policy modes for later implementation:

- `AI_ONLY_TEST_MODE`
- `MERGE_WITH_PHYSICAL`
- `PHYSICAL_OVERRIDES_AI`
- `AI_DISABLED_WHEN_PHYSICAL_ACTIVE`

The exact default is deferred, but physical input must be observable enough to avoid surprising merged states if coexistence is supported.

The first prototype may intentionally support only a simple, explicit test mode.

## 10. Observation bundle

A useful higher-level operation is a bundled observation:

```text
ObservationBundle
- session
- semantic snapshot
- frame metadata
- screenshot
- bridge health
```

The purpose is not to claim atomicity. The purpose is to make one control-loop sample easy to consume while preserving timestamps/sequences for each component.

## 11. Recovery ladder

A future agent should use bounded recovery stages rather than escalating immediately.

Recommended conceptual ladder:

1. Re-observe.
2. Confirm session generation.
3. Neutralize injected input.
4. Retry only an action proven safe to repeat.
5. Re-establish bridge session.
6. Reacquire runtime state from scratch.
7. Stop autonomous control and request manual intervention.

Restarting software or modifying firmware should not be an automatic generic recovery action.

## 12. Logging and replay

The bridge should eventually be able to record a trace containing:

```text
session events
observation metadata
optional screenshots or frame references
MCP/tool request
normalized action
PSP acknowledgement
verification result
errors
```

This trace is valuable for:

- debugging agent mistakes;
- differentiating vision failure from control failure;
- deterministic bridge tests;
- building future test fixtures;
- measuring control-loop latency.

The trace format should avoid requiring LLM-specific data so it can be reused by non-AI tooling.

## 13. Design rule

When choosing between adding another action primitive and adding better state observability, prefer observability unless the missing action is a hard blocker.

The expected failure mode of early versions is not "the AI cannot press CROSS". It is "the AI cannot prove what happened after it pressed CROSS".