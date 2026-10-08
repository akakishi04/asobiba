package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.mixin.AbstractArrowPierceAccessor;
import net.minecraft.tags.EntityTypeTags;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.neoforged.neoforge.common.damagesource.DamageContainer;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.minecraft.world.entity.LightningBolt;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.HitResult;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.entity.ProjectileImpactEvent;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ItemStack;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;

/**
 * Projectile-specific effects use the exact ammunition ItemStack already
 * stored by vanilla AbstractArrow, not the launching weapon's enchantments.
 * This preserves the accepted launcher/ammunition source separation.
 */
public final class EnchantedArrowImpactEvents {
    private static final String POWER = "minecraft:power";
    private static final String WIND_BURST = "minecraft:wind_burst";
    private static final String CHANNELING = "minecraft:channeling";
    private static final String SHARPNESS = "minecraft:sharpness";
    private static final String SMITE = "minecraft:smite";
    private static final String BANE = "minecraft:bane_of_arthropods";
    private static final String IMPALING = "minecraft:impaling";
    private static final String FLAME = "minecraft:flame";
    private static final String PIERCING = "minecraft:piercing";
    private static final String PUNCH = "minecraft:punch";
    private static final String BREACH = "minecraft:breach";

    @SubscribeEvent
    public void onArrowJoined(EntityJoinLevelEvent event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || event.getLevel().isClientSide()
                || !(event.getEntity() instanceof AbstractArrow arrow)) return;

        ItemStack ammo = arrow.getPickupItemStackOrigin();
        int pierce = level(ammo, PIERCING);
        if (pierce > arrow.getPierceLevel()) {
            // Vanilla pierce level N means up to N+1 valid entity hits.
            ((AbstractArrowPierceAccessor)arrow).asobibatweaks$setPierceLevel(
                    (byte)Math.min(127, pierce));
        }
    }

    @SubscribeEvent
    public void onEnchantedArrowHit(LivingIncomingDamageEvent event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !(event.getSource().getDirectEntity() instanceof AbstractArrow arrow)
                || arrow.level().isClientSide()
                || event.getAmount() <= 0.0F) return;

        ItemStack ammo = arrow.getPickupItemStackOrigin();
        if (ammo.isEmpty()) return;

        double extra = 0.0D;
        int sharp = level(ammo, SHARPNESS);
        if (sharp > 0) extra += 1.0D + 0.5D * (sharp - 1);

        int smite = level(ammo, SMITE);
        if (smite > 0 && event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_SMITE)) {
            extra += 2.5D * smite;
        }

        int bane = level(ammo, BANE);
        if (bane > 0 && event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_BANE_OF_ARTHROPODS)) {
            extra += 2.5D * bane;
            // Match vanilla Bane's 1.5s floor, +0.5s per level upper range.
            int duration = 30 + arrow.getRandom().nextInt(Math.max(1, 10 * Math.min(100, bane) + 1));
            event.getEntity().addEffect(
                    new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, duration, 3));
        }

        int impaling = level(ammo, IMPALING);
        if (impaling > 0 && event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_IMPALING)) {
            extra += 2.5D * impaling;
        }


        /*
         * Ammo Breach reduces the vanilla armor mitigation, not the damage
         * after mitigation. Bow/Crossbow Breach must not stack with an ammo
         * Breach of the same strength, so compensate only the stronger level.
         */
        int ammoBreach = Math.min(10, level(ammo, BREACH));
        if (ammoBreach > 0) {
            ItemStack launcher = event.getSource().getWeaponItem();
            int launcherBreach = launcher == null ? 0 : Math.min(10, level(launcher, BREACH));
            if (ammoBreach > launcherBreach) {
                float arrowEfficiency = Math.max(0.0F, 1.0F - ammoBreach * 0.15F);
                float weaponEfficiency = Math.max(0.0F, 1.0F - launcherBreach * 0.15F);
                float factor = weaponEfficiency <= 0.0F
                        ? 1.0F : arrowEfficiency / weaponEfficiency;
                event.addReductionModifier(
                        DamageContainer.Reduction.ARMOR,
                        (container, reduction) -> reduction * Math.max(0.0F, Math.min(1.0F, factor))
                );
            }
        }

        // Arrow-side Flame is intentionally limited to level I.
        if (level(ammo, FLAME) > 0) {
            event.getEntity().setRemainingFireTicks(
                    Math.max(event.getEntity().getRemainingFireTicks(), 100));
        }

        if (extra > 0.0D) {
            event.setAmount((float)Math.min(Float.MAX_VALUE,
                    (double)event.getAmount() + extra));
        }
    }


    /**
     * Restore only the part of vanilla air drag removed by arrow-side Power.
     * Vanilla arrow drag is 0.99 in air, not in water. Gravity remains 0.05
     * per tick and is compensated separately from the velocity drag term.
     */
    @SubscribeEvent
    public void onArrowTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof AbstractArrow arrow)
                || arrow.level().isClientSide() || arrow.isInWater() || arrow.isInLava()
                || arrow.isNoPhysics()
                || ((AbstractArrowPierceAccessor)arrow).asobibatweaks$isInGround()) return;

        int power = level(arrow.getPickupItemStackOrigin(), POWER);
        if (power <= 0) return;

        Vec3 motion = arrow.getDeltaMovement();
        if (motion.lengthSqr() < 1.0E-10D) return;

        double reduction = 0.08D * Math.min(10, power);
        double originalDrag = 0.99D;
        double desiredDrag = originalDrag + (1.0D - originalDrag) * reduction;
        double correction = desiredDrag / originalDrag;
        double gravity = arrow.isNoGravity() ? 0.0D : 0.05D;

        arrow.setDeltaMovement(
                motion.x * correction,
                (motion.y + gravity) * correction - gravity,
                motion.z * correction
        );
        arrow.hurtMarked = true;
    }

    /**
     * Impact-triggered area and weather effects run on entity and block
     * impacts. Piercing hits may trigger again, as explicitly accepted.
     */
    @SubscribeEvent
    public void onProjectileImpact(ProjectileImpactEvent event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || event.isCanceled()
                || !(event.getProjectile() instanceof AbstractArrow arrow)
                || !(arrow.level() instanceof ServerLevel server)) return;

        ItemStack ammo = arrow.getPickupItemStackOrigin();
        if (ammo.isEmpty()) return;
        HitResult hitResult = event.getRayTraceResult();
        if (hitResult == null || hitResult.getType() == HitResult.Type.MISS) return;
        Vec3 point = hitResult.getLocation();

        int wind = Math.min(10, level(ammo, WIND_BURST));
        if (wind > 0) {
            double radius = 2.5D + 0.25D * (wind - 1);
            double force = 1.0D + 0.10D * (wind - 1);
            AABB volume = new AABB(point, point).inflate(radius);
            for (Entity entity : server.getEntitiesOfClass(
                    Entity.class, volume,
                    candidate -> candidate != arrow && candidate.isAlive())) {
                Vec3 away = entity.position().subtract(point);
                double distance = away.length();
                if (distance > radius) continue;

                Vec3 unit = distance > 0.01D
                        ? away.scale(1.0D / distance)
                        : new Vec3(0.0D, 1.0D, 0.0D);
                double falloff = Math.max(0.15D, 1.0D - distance / radius);
                double impulse = force * falloff * 0.55D;
                entity.push(unit.x * impulse,
                        Math.max(0.10D, unit.y * impulse + 0.20D * falloff),
                        unit.z * impulse);
                entity.hurtMarked = true;
            }
        }

        if (level(ammo, CHANNELING) > 0
                && server.isThundering()
                && server.canSeeSky(BlockPos.containing(point).above())) {
            LightningBolt bolt = EntityType.LIGHTNING_BOLT.create(server);
            if (bolt != null) {
                bolt.setPos(point.x, point.y, point.z);
                server.addFreshEntity(bolt);
            }
        }
    }


    /**
     * Only successful, health-damaging projectile hits apply ammo Punch.
     * The launcher's existing Punch knockback will still be applied by the
     * vanilla arrow, so add only the missing difference (max, not sum).
     */
    @SubscribeEvent
    public void onArrowPunch(LivingDamageEvent.Post event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || !(event.getSource().getDirectEntity() instanceof AbstractArrow arrow)
                || arrow.level().isClientSide()) return;

        ItemStack ammo = arrow.getPickupItemStackOrigin();
        int ammoPunch = Math.min(10, level(ammo, PUNCH));
        if (ammoPunch <= 0) return;

        ItemStack launcher = event.getSource().getWeaponItem();
        int launcherPunch = launcher == null ? 0 : Math.min(10, level(launcher, PUNCH));

        double difference = punchPower(ammoPunch) - punchPower(launcherPunch);
        if (difference <= 0.0D) return;

        Vec3 horizontal = arrow.getDeltaMovement().multiply(1.0D, 0.0D, 1.0D);
        if (horizontal.lengthSqr() < 1.0E-8D) return;
        Vec3 direction = horizontal.normalize();

        double resistance = Math.min(1.0D, Math.max(0.0D,
                event.getEntity().getAttributeValue(Attributes.KNOCKBACK_RESISTANCE)));
        double impulse = difference * 0.6D * (1.0D - resistance);
        if (impulse <= 0.0D) return;

        event.getEntity().push(direction.x * impulse,
                Math.min(0.10D, impulse * 0.1D),
                direction.z * impulse);
        event.getEntity().hurtMarked = true;
    }

    private static double punchPower(int level) {
        if (level <= 0) return 0.0D;
        if (level <= 2) return level;
        return 2.0D + 0.5D * (level - 2);
    }

    public static int level(ItemStack arrow, String id) {
        if (arrow.isEmpty()) return 0;
        for (var entry : EnchantmentMasteryData.enchantments(arrow).entrySet()) {
            if (id.equals(EnchantmentMasteryData.id(entry.getKey()))) {
                return Math.max(0, entry.getIntValue());
            }
        }
        return 0;
    }
}
