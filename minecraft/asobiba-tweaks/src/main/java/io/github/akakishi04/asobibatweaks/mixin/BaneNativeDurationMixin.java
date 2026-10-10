package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import io.github.akakishi04.asobibatweaks.feature.NativeEnchantmentEffectMastery;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.enchantment.EnchantedItemInUse;
import net.minecraft.world.item.enchantment.effects.ApplyMobEffect;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

@Mixin(ApplyMobEffect.class)
public abstract class BaneNativeDurationMixin {
    @ModifyExpressionValue(method = "apply", at = @At(value = "INVOKE", target = "Ljava/lang/Math;round(F)I", ordinal = 0))
    private int asobibatweaks$nativeSlow(int ticks, ServerLevel level, int enchantmentLevel,
                                       EnchantedItemInUse item, Entity entity, Vec3 origin) {
        return NativeEnchantmentEffectMastery.baneDuration(this, level, item, ticks);
    }
}
