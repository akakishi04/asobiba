package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.FeatherFallingMasteryEvents;
import io.github.akakishi04.asobibatweaks.feature.MaceMasteryEvents;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** Scale only ordinary input acceleration, never gravity or existing velocity. */
@Mixin(Entity.class)
public abstract class FeatherFallingAirControlMixin {
    @ModifyVariable(method = "moveRelative", at = @At("HEAD"), argsOnly = true, ordinal = 0)
    private float asobibatweaks$featherAirControl(float vanilla) {
        return (Object)this instanceof Player player
                ? MaceMasteryEvents.aerialInputSpeed(player, vanilla,
                        FeatherFallingMasteryEvents.aerialInputSpeed(player, vanilla)) : vanilla;
    }
}
