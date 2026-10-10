package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.MaceItem;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;
import net.neoforged.neoforge.event.level.ExplosionKnockbackEvent;
import net.neoforged.neoforge.network.PacketDistributor;
import net.neoforged.neoforge.network.registration.NetworkRegistry;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;

/**
 * Mace-only Density and Wind Burst mastery. Extra impact damage is derived
 * from the vanilla per-fallen-block Density contribution, and never from
 * the full attack damage (which already includes that contribution).
 */
public final class MaceMasteryEvents {
    private static final String CONTROL_UNTIL = "asobibatweaks_wind_aerial_control_until";
    private static final String CONTROL_STRENGTH = "asobibatweaks_wind_aerial_control_scale";
    private record BurstScope(ServerPlayer player, LauncherReloadMasteryEvents.Branch branch) {}
    private static final ThreadLocal<BurstScope> WIND_BURST = new ThreadLocal<>();

    /** Scope only the registry's real Wind Burst post-attack effect, retaining native conditions. */
    public static void withWindBurst(ServerPlayer player, ItemStack stack, Runnable nativeEffect) {
        BurstScope previous = WIND_BURST.get();
        var branch = mastery(stack, "minecraft:wind_burst");
        if (branch == null) WIND_BURST.remove();
        else WIND_BURST.set(new BurstScope(player, branch));
        try { nativeEffect.run(); }
        finally {
            if (previous == null) WIND_BURST.remove();
            else WIND_BURST.set(previous);
        }
    }

    @SubscribeEvent
    public void onWindBurstLaunch(ExplosionKnockbackEvent event) {
        BurstScope scope = WIND_BURST.get();
        if (scope == null || event.getAffectedEntity() != scope.player()) return;
        Vec3 nativeImpulse = event.getKnockbackVelocity();
        if (nativeImpulse.lengthSqr() <= 0.00000001D) return;
        var b = scope.branch();
        if (b.choice() == 0) {
            event.setKnockbackVelocity(nativeImpulse.multiply(1.0D, 1.10D + 0.20D * b.progress(), 1.0D));
        } else if (b.choice() == 2) {
            // Scale only this launch, not pre-existing motion. The event's vector is
            // used by both server motion and the original client explosion packet.
            event.setKnockbackVelocity(nativeImpulse.scale(0.90D));
            double strength = 0.25D + 0.45D * b.progress();
            applyAerialControl(scope.player(), strength, 35);
            // Real client physics needs this window, but mock/unnegotiated
            // connections cannot receive custom payloads.
            if (scope.player().connection != null && NetworkRegistry.hasChannel(
                    scope.player().connection, WindAerialControlPayload.TYPE.id())) {
                PacketDistributor.sendToPlayer(scope.player(), new WindAerialControlPayload((float)strength, 35));
            }
        }
    }

    private static final ThreadLocal<Boolean> SHOCK_ACTIVE =
            ThreadLocal.withInitial(() -> false);

    private static LauncherReloadMasteryEvents.Branch mastery(ItemStack stack, String id) {
        return stack.is(Items.MACE)
                ? LauncherReloadMasteryEvents.branch(stack, id) : null;
    }

    private static boolean smash(ServerPlayer player) {
        return player.fallDistance >= 1.5F && MaceItem.canSmashAttack(player);
    }

    @SubscribeEvent
    public void onMaceIncoming(LivingIncomingDamageEvent event) {
        if (SHOCK_ACTIVE.get() || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0
                || !(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || !smash(player)) return;

        ItemStack mace = player.getMainHandItem();
        var branch = mastery(mace, "minecraft:density");
        if (branch == null || branch.choice() == 2) return;

        int level = EnchantedArrowImpactEvents.level(mace, "minecraft:density");
        if (level <= 0) return;
        double fall = Math.max(0.0D, player.fallDistance);
        double densityPerBlock = 0.5D * Math.min(10, level);
        double growth = branch.progress();
        double extra = branch.choice() == 0
                ? Math.max(0.0D, fall - 8.0D) * densityPerBlock *
                        (0.10D + 0.15D * growth)
                : Math.min(8.0D, fall) * densityPerBlock *
                        (0.15D + 0.35D * growth);
        if (extra > 0.0D) {
            event.setAmount((float)Math.min(Float.MAX_VALUE, event.getAmount() + extra));
        }
    }

    @SubscribeEvent
    public void onMaceHit(LivingDamageEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F || SHOCK_ACTIVE.get()
                || !(event.getSource().getEntity() instanceof ServerPlayer attacker)
                || event.getSource().getDirectEntity() != attacker
                || !smash(attacker)) return;

        ItemStack mace = attacker.getMainHandItem();
        if (!mace.is(Items.MACE) || !(attacker.level() instanceof ServerLevel world)) return;
        var density = mastery(mace, "minecraft:density");
        var wind = mastery(mace, "minecraft:wind_burst");

        if (density != null && density.choice() == 2) {
            int level = EnchantedArrowImpactEvents.level(mace, "minecraft:density");
            double densityBonus = 0.5D * Math.min(10, level) *
                    Math.max(0.0D, attacker.fallDistance);
            double strength = 0.15D + 0.20D * density.progress();
            double echo = Math.min(6.0D, densityBonus * strength);
            if (echo > 0.1D) {
                SHOCK_ACTIVE.set(true);
                try {
                    double radius = 2.0D + 1.5D * density.progress();
                    for (LivingEntity other : world.getEntitiesOfClass(
                            LivingEntity.class,
                            event.getEntity().getBoundingBox().inflate(radius),
                            target -> target.isAlive() && target != attacker
                                    && target != event.getEntity()
                                    && !target.isAlliedTo(attacker))) {
                        other.hurt(attacker.damageSources().playerAttack(attacker), (float)echo);
                    }
                } finally {
                    SHOCK_ACTIVE.remove();
                }
            }
        }

        if (wind == null
                || EnchantedArrowImpactEvents.level(mace, "minecraft:wind_burst") <= 0) {
            return;
        }

        double progress = wind.progress();
        if (wind.choice() == 1) {
            double radius = 3.0D + 0.5D + 1.5D * progress;
            double bonusImpulse = 0.10D + 0.15D * progress;
            for (LivingEntity other : world.getEntitiesOfClass(
                    LivingEntity.class,
                    event.getEntity().getBoundingBox().inflate(radius),
                    candidate -> candidate != attacker && candidate != event.getEntity()
                            && candidate.isAlive() && !candidate.isAlliedTo(attacker))) {
                Vec3 delta = other.position().subtract(event.getEntity().position())
                        .multiply(1.0D, 0.0D, 1.0D);
                if (delta.lengthSqr() <= 0.00001D || delta.lengthSqr() > radius * radius) continue;
                Vec3 impulse = delta.normalize().scale(
                        bonusImpulse * Math.max(0.25D, 1.0D - delta.length() / radius));
                other.push(impulse.x, 0.1D, impulse.z);
                other.hurtMarked = true;
            }

        }
    }

    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        event.registrar("1").playToClient(WindAerialControlPayload.TYPE,
                WindAerialControlPayload.STREAM_CODEC,
                (payload, context) -> context.enqueueWork(() ->
                        applyAerialControl(context.player(), payload.strength(), payload.ticks())));
    }

    private static void applyAerialControl(Player player, double strength, int ticks) {
        if (!Double.isFinite(strength)) return;
        CompoundTag data = player.getPersistentData();
        data.putLong(CONTROL_UNTIL, player.level().getGameTime() + Math.clamp(ticks, 0, 35));
        data.putDouble(CONTROL_STRENGTH, Math.clamp(strength, 0.0D, 0.70D));
    }

    /** Strongest-only composition with Feather Falling: never multiply two control bonuses.
     * This runs on both sides; the burst synchronizes a bounded window to its owner. */
    public static float aerialInputSpeed(Player player, float vanilla, float featherAdjusted) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || vanilla <= 0.0F || player.onGround() || !player.isAlive()
                || player.isInWater() || player.isInLava() || player.onClimbable()
                || player.isFallFlying() || player.isAutoSpinAttack() || player.isPassenger()
                || player.getAbilities().flying || player.isSpectator()) return featherAdjusted;
        CompoundTag state = player.getPersistentData();
        if (state.getLong(CONTROL_UNTIL) <= player.level().getGameTime()) {
            state.remove(CONTROL_UNTIL);
            state.remove(CONTROL_STRENGTH);
            return featherAdjusted;
        }
        double strength = Math.clamp(state.getDouble(CONTROL_STRENGTH), 0.0D, 0.70D);
        return (float)Math.max(featherAdjusted, vanilla * (1.0D + strength));
    }
}
