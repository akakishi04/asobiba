package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.entity.monster.Creeper;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Creeper.class)
public abstract class GiantCreeperMixin {
    @Shadow
    private int explosionRadius;

    @Unique
    private int asobibatweaks$originalExplosionRadius;

    @Inject(method = "explodeCreeper", at = @At("HEAD"))
    private void asobibatweaks$amplifyGiantExplosion(CallbackInfo ci) {
        Creeper self = (Creeper)(Object)this;
        if (!AsobibaTweaksConfig.GIANT_MOBS_ENABLED.getAsBoolean()
                || !self.getPersistentData().getBoolean("asobibatweaks_giant_mob")) {
            return;
        }

        asobibatweaks$originalExplosionRadius = explosionRadius;
        double scale = Math.max(1.0D, self.getPersistentData().getDouble("asobibatweaks_giant_scale"));
        explosionRadius = Math.max(explosionRadius + 1,
                (int)Math.round(explosionRadius * (1.0D + (scale - 1.0D) * 0.45D)));
        self.getPersistentData().putDouble("asobibatweaks_tnt_wind",
                1.0D + (scale - 1.0D) * 0.55D);
    }

    @Inject(method = "explodeCreeper", at = @At("RETURN"))
    private void asobibatweaks$restoreExplosionRadius(CallbackInfo ci) {
        Creeper self = (Creeper)(Object)this;
        if (asobibatweaks$originalExplosionRadius > 0) {
            explosionRadius = asobibatweaks$originalExplosionRadius;
            asobibatweaks$originalExplosionRadius = 0;
        }
        self.getPersistentData().remove("asobibatweaks_tnt_wind");
    }
}
