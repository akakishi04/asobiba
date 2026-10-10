package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.enchantment.EnchantedItemInUse;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentEffectComponents;
import net.minecraft.world.item.enchantment.Enchantments;

/** Adjust the actual registered native effect, after its random rolls and conditions. */
public final class NativeEnchantmentEffectMastery {
    private NativeEnchantmentEffectMastery() {}

    public static boolean isEffect(ServerLevel level, ResourceKey<Enchantment> key, Object effect) {
        var enchantment = level.registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(key);
        return enchantment.value().getEffects(EnchantmentEffectComponents.POST_ATTACK)
                .stream().anyMatch(entry -> entry.effect() == effect);
    }

    public static float fireDuration(Object effect, ServerLevel level, EnchantedItemInUse item,
                                     Entity target, float seconds) {
        if (!isEffect(level, Enchantments.FIRE_ASPECT, effect)) return seconds;
        var branch = LauncherReloadMasteryEvents.branch(item.itemStack(), "minecraft:fire_aspect");
        if (branch == null) return seconds;
        double progress = branch.progress();
        float duration = branch.choice() == 0 ? (float)(seconds * (1.25D + 0.50D * progress))
                : branch.choice() == 1 ? seconds * 0.60F : seconds;
        var state = target.getPersistentData();
        long end = level.getGameTime() + Math.max(1, Math.round(duration * 20.0F));
        if (branch.choice() == 1) {
            state.putLong("asobibatweaks_fire_aspect_flash_until", end);
            state.putInt("asobibatweaks_fire_aspect_flash_multiplier", (int)Math.round((1.20D + 0.40D * progress) * 1000));
        } else if (branch.choice() == 2) {
            state.putLong("asobibatweaks_fire_aspect_cauterize_until", end);
            state.putInt("asobibatweaks_fire_aspect_cauterize_reduction", (int)Math.round((0.10D + 0.20D * progress) * 1000));
        }
        return duration;
    }

    public static int baneDuration(Object effect, ServerLevel level, EnchantedItemInUse item, int ticks) {
        if (!isEffect(level, Enchantments.BANE_OF_ARTHROPODS, effect)) return ticks;
        var branch = LauncherReloadMasteryEvents.branch(item.itemStack(), "minecraft:bane_of_arthropods");
        return branch == null || branch.choice() != 0 ? ticks
                : (int)Math.min(Integer.MAX_VALUE, Math.round(ticks * (1.25D + 0.75D * branch.progress())));
    }
}
