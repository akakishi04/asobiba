package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.DailyPlayTimeService;
import net.minecraft.server.MinecraftServer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** The outer loop runs even when IntegratedServer skips ordinary tick events while paused. */
@Mixin(MinecraftServer.class)
public abstract class DailyPlayTimeServerMixin {
    @Inject(method = "runServer", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/server/MinecraftServer;tickServer(Ljava/util/function/BooleanSupplier;)V",
            shift = At.Shift.AFTER))
    private void asobibatweaks$sampleOnlineRealTime(CallbackInfo ci) {
        DailyPlayTimeService.onServerLoop((MinecraftServer) (Object) this);
    }
}
