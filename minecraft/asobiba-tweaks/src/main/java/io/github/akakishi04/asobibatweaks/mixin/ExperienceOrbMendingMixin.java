package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.MendingExtendedEvents;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.ExperienceOrb;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(ExperienceOrb.class)
public abstract class ExperienceOrbMendingMixin {
    @Inject(method = "repairPlayerItems", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$distributeMendingXp(
            ServerPlayer player, int available, CallbackInfoReturnable<Integer> cir) {
        int left = MendingExtendedEvents.distribute(player, available);
        if (left >= 0) cir.setReturnValue(left);
    }
}
