package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.inventory.AnvilMenu;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.Constant;
import org.spongepowered.asm.mixin.injection.ModifyConstant;

@Mixin(AnvilMenu.class)
public abstract class AnvilMenuMixin {
    @ModifyConstant(method = "createResult", constant = @Constant(intValue = 40))
    private int asobibatweaks$removeTooExpensiveLimit(int original) {
        return AsobibaTweaksConfig.UNCAPPED_ANVIL_ENABLED.getAsBoolean() ? Integer.MAX_VALUE : original;
    }
}
