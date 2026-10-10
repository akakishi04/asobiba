package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.item.Items;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ArmorStand.class)
public abstract class ArmorStandElytraMixin {
    @Inject(method = "tick", at = @At("TAIL"))
    private void asobibatweaks$openDisplayedElytra(CallbackInfo ci) {
        ArmorStand self = (ArmorStand)(Object)this;
        boolean open = AsobibaTweaksConfig.ELYTRA_DISPLAY_ENABLED.getAsBoolean()
                && self.getItemBySlot(EquipmentSlot.CHEST).is(Items.ELYTRA);
        ((EntitySharedFlagAccessor)(Object)self).asobibatweaks$setSharedFlag(7, open);
    }
}
