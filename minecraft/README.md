# Minecraft mods in asobiba

Target environment:

- Minecraft 1.21.1
- NeoForge 21.1.219
- Java 21

Projects:

- `asobiba-tweaks/` — small gameplay experiments collected behind config toggles.
- `minecraft-data-logger/` — LLM/agent-oriented gameplay telemetry logger.

Both projects use NeoForge ModDevGradle and intentionally remain independent JARs.

## Build

From either project directory:

```powershell
gradle build
```

If no system Gradle is installed, generate/copy a Gradle wrapper from the NeoForge 1.21.1 MDK once and use `./gradlew build`.

## Status

v0.1 bootstrap is single-player-first. The configuration screens edit COMMON config in the same JVM. Dedicated-server config sync is deliberately deferred rather than pretending client-side toggles are server-authoritative.
