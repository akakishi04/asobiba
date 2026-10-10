package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.InfinityMasteryEvents;
import io.github.akakishi04.asobibatweaks.feature.LauncherReloadMasteryEvents;
import java.util.List;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.ProjectileWeaponItem;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.jetbrains.annotations.Nullable;

@Mixin(ProjectileWeaponItem.class)
public abstract class ProjectileWeaponInfinityMixin {
    @Inject(method = "shoot", at = @At("HEAD"))
    private void asobibatweaks$trackInfinityShot(
            ServerLevel level, LivingEntity shooter, InteractionHand hand,
            ItemStack weapon, List<ItemStack> projectiles,
            float velocity, float inaccuracy, boolean isCritical,
            @Nullable LivingEntity target, CallbackInfo ci) {
        InfinityMasteryEvents.recordShot(level, shooter, weapon, projectiles, velocity);
        LauncherReloadMasteryEvents.onFired(level, shooter, weapon);
    }
}
