package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.mixin.AbstractArrowPierceAccessor;
import net.minecraft.tags.EntityTypeTags;
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
    private static final String SHARPNESS = "minecraft:sharpness";
    private static final String SMITE = "minecraft:smite";
    private static final String BANE = "minecraft:bane_of_arthropods";
    private static final String IMPALING = "minecraft:impaling";
    private static final String FLAME = "minecraft:flame";
    private static final String PIERCING = "minecraft:piercing";

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
