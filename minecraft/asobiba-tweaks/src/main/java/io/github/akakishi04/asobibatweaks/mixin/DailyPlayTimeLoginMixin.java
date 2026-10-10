package io.github.akakishi04.asobibatweaks.mixin;

import com.mojang.authlib.GameProfile;
import io.github.akakishi04.asobibatweaks.feature.DailyPlayTimeService;
import java.net.SocketAddress;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.players.PlayerList;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Preserve vanilla ban/whitelist/capacity decisions; reject exhausted UUIDs before placement. */
@Mixin(PlayerList.class)
public abstract class DailyPlayTimeLoginMixin {
    @Shadow @Final private MinecraftServer server;

    @Inject(method = "canPlayerLogin", at = @At("RETURN"), cancellable = true)
    private void asobibatweaks$checkDailyAllowance(SocketAddress address, GameProfile profile,
                                                 CallbackInfoReturnable<Component> cir) {
        if (cir.getReturnValue() != null || profile.getId() == null) return;
        Component rejection = DailyPlayTimeService.loginRejection(server, profile.getId());
        if (rejection != null) cir.setReturnValue(rejection);
    }
}
