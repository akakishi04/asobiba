package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.EndermanVoidGatheringService;
import io.github.akakishi04.asobibatweaks.feature.VillagerArmorStandImitationService;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.navigation.PathNavigation;
import net.minecraft.world.entity.monster.EnderMan;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Keep a scene's validated finite route from being silently replaced by native A* recomputation. */
@Mixin(PathNavigation.class)
public abstract class EndermanVoidNavigationMixin implements EndermanVoidGatheringService.IdleNavigationState {
    @Shadow @Final protected Mob mob;
    @Shadow protected boolean hasDelayedRecomputation;
    @Shadow private BlockPos targetPos;

    @Override
    @Unique
    public void clearIdleRecomputation() {
        hasDelayedRecomputation = false;
        targetPos = null;
    }

    @Inject(method = "recomputePath", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$preserveValidatedSceneRoute(CallbackInfo ci) {
        if (mob instanceof EnderMan enderman && EndermanVoidGatheringService.ownsNavigation(enderman)
                || mob instanceof Villager villager && VillagerArmorStandImitationService.ownsNavigation(villager)) {
            // The scene revalidates its supported footprint before movement and cancels on edits.
            // Never intercept a replacement path owned by another goal or any unowned navigator.
            hasDelayedRecomputation = false;
            ci.cancel();
        }
    }
}
