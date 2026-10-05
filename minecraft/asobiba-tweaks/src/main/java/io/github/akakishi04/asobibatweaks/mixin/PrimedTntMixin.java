package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.entity.item.PrimedTnt;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(PrimedTnt.class)
public abstract class PrimedTntMixin {
    @Inject(method = "explode", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$designedExplosion(CallbackInfo ci) {
        if (!AsobibaTweaksConfig.TNT_DESIGN_ENABLED.getAsBoolean()) return;

        PrimedTnt self = (PrimedTnt)(Object)this;
        if (!self.getPersistentData().contains("asobibatweaks_tnt_power")) return;

        float power = self.getPersistentData().getFloat("asobibatweaks_tnt_power");
        boolean preserve = self.getPersistentData().getBoolean("asobibatweaks_tnt_preserve_blocks");
        boolean fire = self.getPersistentData().getBoolean("asobibatweaks_tnt_fire");
        self.level().explode(
                self,
                self.getX(),
                self.getY(0.0625D),
                self.getZ(),
                Math.max(0.5F, power),
                fire,
                preserve ? Level.ExplosionInteraction.NONE : Level.ExplosionInteraction.TNT
        );
        ci.cancel();
    }
}
