# Asobiba Tweaks

A collection of small optional gameplay ideas.

## v0.1 features

### Growing Items

Enabled by default.

- Durable vanilla items gain growth XP from block breaking and kills.
- The XP and level are stored on the individual ItemStack in `minecraft:custom_data`.
- Item tooltip shows growth level and XP.
- Higher levels grant a small chance to repair one durability point when XP is earned.
- Maximum level and XP scale are configurable.

### Play Time Limit

Disabled by default.

- Counts active server ticks for each login session.
- Configurable minute limit.
- Configurable warning time.
- Mode can be `WARN_ONLY` or `DISCONNECT`.
- Session state is intentionally not persisted in v0.1.

## Configuration UI

Open **Mods -> Asobiba Tweaks -> Config**. NeoForge's native configuration screen is used, so new config entries automatically appear without maintaining a second custom UI.

## Next

The best next feature is Item Personality: roll one trait at growth milestones, while keeping the trait data on the item itself.
