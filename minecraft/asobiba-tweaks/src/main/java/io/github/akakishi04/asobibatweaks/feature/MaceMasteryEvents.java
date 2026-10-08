package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.MaceItem;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/**
 * Mace-only Density and Wind Burst mastery. Extra impact damage is derived
 * from the vanilla per-fallen-block Density contribution, and never from
 * the full attack damage (which already includes that contribution).
 */
public final class MaceMasteryEvents {
    private static final String CONTROL_UNTIL = "asobibatweaks_wind_aerial_control_until";
    private static final String CONTROL_STRENGTH = "asobibatweaks_wind_aerial_control_scale";
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
        if (wind.choice() == 0) {
            // Add a bounded part of the vanilla updraft after a valid smash.
            double lift = 0.10D + 0.30D * progress;
            attacker.push(0.0D, lift, 0.0D);
            attacker.hurtMarked = true;
        } else if (wind.choice() == 1) {
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
        } else if (wind.choice() == 2) {
            CompoundTag data = attacker.getPersistentData();
            data.putLong(CONTROL_UNTIL, world.getGameTime() + 35L);
            data.putDouble(CONTROL_STRENGTH, 0.25D + 0.45D * progress);
        }
    }

    @SubscribeEvent
    public void onAerialSteering(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.onGround() || !player.isAlive()) return;
        CompoundTag state = player.getPersistentData();
        long deadline = state.getLong(CONTROL_UNTIL);
        if (deadline <= player.level().getGameTime()) {
            state.remove(CONTROL_UNTIL);
            state.remove(CONTROL_STRENGTH);
            return;
        }
        double strength = Math.min(0.70D, state.getDouble(CONTROL_STRENGTH));
        Vec3 facing = player.getLookAngle().multiply(1.0D, 0.0D, 1.0D);
        if (facing.lengthSqr() <= 0.0001D) return;
        Vec3 current = player.getDeltaMovement();
        Vec3 steer = facing.normalize().scale(0.018D * strength);
        if (current.horizontalDistanceSqr() < 0.75D * 0.75D) {
            player.setDeltaMovement(current.x + steer.x, current.y,
                    current.z + steer.z);
            player.hurtMarked = true;
        }
    }
}
