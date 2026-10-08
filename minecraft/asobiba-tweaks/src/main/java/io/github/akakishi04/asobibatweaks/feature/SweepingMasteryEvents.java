package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.SweepAttackEvent;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/**
 * Sweeping Edge sidegrades observe one actual vanilla/NeoForge sweep and
 * never create synthetic damage on extra entities.
 */
public final class SweepingMasteryEvents {
    private static final String SWEEP_STARTED = "asobibatweaks_sweep_started";
    private static final String SWEEP_PRIMARY = "asobibatweaks_sweep_primary_id";
    private static final String SWEEP_SECONDARIES = "asobibatweaks_sweep_secondary_hits";
    private static final String RHYTHM_UNTIL = "asobibatweaks_sweep_rhythm_until";

    private static LauncherReloadMasteryEvents.Branch branch(ItemStack stack) {
        return LauncherReloadMasteryEvents.branch(stack, "minecraft:sweeping_edge");
    }

    public static AABB adjustHitBox(Player player, Entity target, AABB original) {
        var b = branch(player.getMainHandItem());
        if (b == null) return original;
        if (b.choice() == 0) {
            double expansion = 0.10D + 0.20D * b.progress();
            return original.inflate(expansion, 0.0D, expansion);
        }
        if (b.choice() == 1) {
            double smaller = 0.25D;
            return original.deflate(smaller, 0.0D, smaller);
        }
        return original;
    }

    @SubscribeEvent
    public void onAttackSweep(SweepAttackEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) return;
        CompoundTag data = player.getPersistentData();
        var b = branch(player.getMainHandItem());
        if (!event.isSweeping() || b == null) {
            data.remove(SWEEP_STARTED);
            data.remove(SWEEP_SECONDARIES);
            return;
        }
        data.putLong(SWEEP_STARTED, player.level().getGameTime());
        data.putInt(SWEEP_PRIMARY, event.getTarget().getId());
        data.putInt(SWEEP_SECONDARIES, 0);
    }

    @SubscribeEvent
    public void onSweepIncoming(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer attacker)
                || event.getSource().getDirectEntity() != attacker
                || event.getAmount() <= 0.0F) return;

        CompoundTag data = attacker.getPersistentData();
        long now = attacker.level().getGameTime();
        var b = branch(attacker.getMainHandItem());
        if (b != null && b.choice() == 1
                && data.getLong(SWEEP_STARTED) == now
                && data.getInt(SWEEP_PRIMARY) != event.getEntity().getId()) {
            double bonus = 0.10D + 0.20D * b.progress();
            event.setAmount((float)Math.min(Float.MAX_VALUE,
                    event.getAmount() * (1.0D + bonus)));
        }

        // Battle Rhythm applies once to a following melee attack, not to
        // the same sweep that earned the rhythm. No stacking across sweeps.
        if (b != null && b.choice() == 2
                && now < data.getLong(RHYTHM_UNTIL)
                && data.getLong(SWEEP_STARTED) != now) {
            double bonus = 0.05D + 0.10D * b.progress();
            event.setAmount((float)Math.min(Float.MAX_VALUE,
                    event.getAmount() * (1.0D + bonus)));
            data.remove(RHYTHM_UNTIL);
        }
    }

    @SubscribeEvent
    public void onSweepDamage(LivingDamageEvent.Post event) {
        if (event.getNewDamage() <= 0.0F
                || !(event.getSource().getEntity() instanceof ServerPlayer attacker)
                || event.getSource().getDirectEntity() != attacker) return;
        CompoundTag data = attacker.getPersistentData();
        if (data.getLong(SWEEP_STARTED) == attacker.level().getGameTime()
                && data.getInt(SWEEP_PRIMARY) != event.getEntity().getId()) {
            data.putInt(SWEEP_SECONDARIES,
                    Math.min(32, data.getInt(SWEEP_SECONDARIES) + 1));
        }
    }

    @SubscribeEvent
    public void afterSweep(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) return;
        CompoundTag data = player.getPersistentData();
        long last = data.getLong(SWEEP_STARTED);
        long now = player.level().getGameTime();
        if (last < now && last > 0L) {
            if (data.getInt(SWEEP_SECONDARIES) >= 2
                    && branch(player.getMainHandItem()) instanceof
                    LauncherReloadMasteryEvents.Branch b
                    && b.choice() == 2) {
                data.putLong(RHYTHM_UNTIL, now + 40L);
            }
            data.remove(SWEEP_STARTED);
            data.remove(SWEEP_SECONDARIES);
        }
    }
}
