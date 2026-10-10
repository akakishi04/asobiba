package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentMasteryData;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.enchantment.EnchantedItemInUse;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.item.enchantment.effects.DamageItem;
import net.minecraft.world.item.enchantment.effects.EnchantmentLocationBasedEffect;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/** Intercept only actual Soul Speed wear, before breakage, with no cross-item damage history. */
@Mixin(Enchantment.class)
public abstract class SoulSpeedWearMixin {
    @WrapOperation(method = "runLocationChangedEffects", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/item/enchantment/effects/EnchantmentLocationBasedEffect;onChangedBlock(Lnet/minecraft/server/level/ServerLevel;ILnet/minecraft/world/item/enchantment/EnchantedItemInUse;Lnet/minecraft/world/entity/Entity;Lnet/minecraft/world/phys/Vec3;Z)V"))
    private void asobibatweaks$conserveSoulWear(
            EnchantmentLocationBasedEffect effect, ServerLevel level, int enchantmentLevel,
            EnchantedItemInUse item, Entity entity, Vec3 position, boolean newlyActive,
            Operation<Void> original) {
        if (AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                && effect instanceof DamageItem && entity instanceof ServerPlayer player) {
            var soulSpeed = level.registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                    .getOrThrow(Enchantments.SOUL_SPEED);
            if ((Object)this == soulSpeed.value()
                    && EnchantmentMasteryData.getBranch(item.itemStack(), soulSpeed) == 0) {
                int mastery = EnchantmentMasteryData.getMastery(item.itemStack(), soulSpeed);
                if (mastery >= 50) {
                    double strength = (Math.min(100, mastery) - 50) / 50.0D;
                    if (player.getRandom().nextDouble() < 0.25D + 0.50D * strength) return;
                }
            }
        }
        original.call(effect, level, enchantmentLevel, item, entity, position, newlyActive);
    }
}
