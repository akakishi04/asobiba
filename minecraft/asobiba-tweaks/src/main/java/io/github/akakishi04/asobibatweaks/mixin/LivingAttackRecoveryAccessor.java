package io.github.akakishi04.asobibatweaks.mixin;

import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** The vanilla cooldown counter is declared by LivingEntity, not Player. */
@Mixin(LivingEntity.class)
public interface LivingAttackRecoveryAccessor {
    @Accessor("attackStrengthTicker") int asobibatweaks$getAttackStrengthTicker();
    @Accessor("attackStrengthTicker") void asobibatweaks$setAttackStrengthTicker(int value);
}
