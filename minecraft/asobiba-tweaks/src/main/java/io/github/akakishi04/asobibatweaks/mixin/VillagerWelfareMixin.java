package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.VillageEconomyService;
import io.github.akakishi04.asobibatweaks.feature.VillagerSimData;
import io.github.akakishi04.asobibatweaks.feature.VillagerWelfareService;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Villager.class)
public abstract class VillagerWelfareMixin {
    @Inject(method = "updateSpecialPrices", at = @At("TAIL"))
    private void asobibatweaks$applyWelfareTradePrices(Player player, CallbackInfo ci) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_WELFARE_ENABLED.getAsBoolean()) return;
        Villager self = (Villager)(Object)this;
        VillagerWelfareService.applyTradePriceModifier(self);
        VillageEconomyService.applyTradePriceModifier(self);
    }

    @Inject(method = "restock", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$blockRestockDuringRefusal(CallbackInfo ci) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_WELFARE_ENABLED.getAsBoolean()) return;
        if (VillagerSimData.refusal((Villager)(Object)this)) {
            ci.cancel();
        }
    }
}
