package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.ChannelingMasteryEvents;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.item.enchantment.EnchantedItemInUse;
import net.minecraft.world.item.enchantment.effects.SummonEntityEffect;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/**
 * Change only the vanilla Channeling lightning's original spawn position.
 * This does NOT add another lightning entity. It changes the Vec3 used for
 * both EntityType.spawn and the subsequent spawned entity positioning.
 */
@Mixin(SummonEntityEffect.class)
public abstract class SummonEntityEffectConductorMixin {
    @ModifyVariable(method = "apply", at = @At("HEAD"), argsOnly = true)
    private Vec3 asobibatweaks$redirectOriginalLightning(
            Vec3 original, ServerLevel level, int enchantmentLevel,
            EnchantedItemInUse item, Entity affected, Vec3 origin) {
        SummonEntityEffect effect = (SummonEntityEffect)(Object)this;
        if (effect.entityTypes().size() != 1
                || effect.entityTypes().stream().noneMatch(holder ->
                        holder.value() == EntityType.LIGHTNING_BOLT)) {
            return original;
        }
        return ChannelingMasteryEvents.redirectConductorLightning(
                level, item, affected, original);
    }
}
