package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.entity.vehicle.AbstractMinecart;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(AbstractMinecart.class)
public abstract class AbstractMinecartMixin {
    @Inject(method = "getMaxSpeedWithRail", at = @At("RETURN"), cancellable = true)
    private void asobibatweaks$removeRailSpeedCeiling(CallbackInfoReturnable<Double> cir) {
        if (AsobibaTweaksConfig.HIGH_SPEED_MINECARTS_ENABLED.getAsBoolean()) {
            cir.setReturnValue(Double.MAX_VALUE);
        }
    }
}
