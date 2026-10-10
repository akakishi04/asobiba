package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.FrostWalkerToggle;
import io.github.akakishi04.asobibatweaks.feature.FrostWalkerMasteryEvents;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.enchantment.EnchantedItemInUse;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.Enchantments;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Suppress only Frost Walker's location-changed effect. Do not remove the
 * enchantment from the ItemStack or its other damage-protection effects.
 */
@Mixin(Enchantment.class)
public abstract class FrostWalkerLocationMixin {
    @Inject(method = "runLocationChangedEffects", at = @At("HEAD"))
    private void asobibatweaks$captureBeforeFreezing(
            ServerLevel world, int level, EnchantedItemInUse context,
            LivingEntity wearer, CallbackInfo ci) {
        if (!(wearer instanceof ServerPlayer player)) return;
        Enchantment walker = world.registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FROST_WALKER).value();
        if ((Object)this == walker
                && FrostWalkerToggle.enabled(player.getItemBySlot(EquipmentSlot.FEET))) {
            FrostWalkerMasteryEvents.before(world, player, level);
        }
    }

    @Inject(method = "runLocationChangedEffects", at = @At("TAIL"))
    private void asobibatweaks$specializeNewIce(
            ServerLevel world, int level, EnchantedItemInUse context,
            LivingEntity wearer, CallbackInfo ci) {
        if (!(wearer instanceof ServerPlayer player)) return;
        Enchantment walker = world.registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FROST_WALKER).value();
        if ((Object)this == walker) FrostWalkerMasteryEvents.after(world, player);
    }

    @Inject(method = "runLocationChangedEffects", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$skipDisabledFrostWalker(
            ServerLevel world, int level, EnchantedItemInUse context,
            LivingEntity wearer, CallbackInfo ci) {
        if (!(wearer instanceof ServerPlayer player)) return;
        Enchantment frostWalker = world.registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FROST_WALKER).value();
        if ((Object)this == frostWalker
                && !FrostWalkerToggle.enabled(player.getItemBySlot(EquipmentSlot.FEET))) {
            ci.cancel();
        }
    }
}
