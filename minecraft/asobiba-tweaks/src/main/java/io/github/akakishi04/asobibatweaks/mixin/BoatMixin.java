package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.OceanAndDisplayEvents;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.vehicle.Boat;
import net.minecraft.world.entity.vehicle.ChestBoat;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(Boat.class)
public abstract class BoatMixin {
    @Inject(method = "canAddPassenger", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$largeBoatPassengerCapacity(Entity passenger, CallbackInfoReturnable<Boolean> cir) {
        Boat self = (Boat)(Object)this;
        if (!AsobibaTweaksConfig.LARGE_BOATS_ENABLED.getAsBoolean()
                || !self.getPersistentData().getBoolean(OceanAndDisplayEvents.LARGE_BOAT)) {
            return;
        }

        int max = self instanceof ChestBoat ? 3 : 4;
        if (self.getPassengers().size() < max) {
            cir.setReturnValue(true);
        }
    }
}
