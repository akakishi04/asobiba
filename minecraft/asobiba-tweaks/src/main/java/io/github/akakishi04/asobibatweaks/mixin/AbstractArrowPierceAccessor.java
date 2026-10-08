package io.github.akakishi04.asobibatweaks.mixin;

import net.minecraft.world.entity.projectile.AbstractArrow;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;

/** Private vanilla piercing setter for already-created arrow entities. */
@Mixin(AbstractArrow.class)
public interface AbstractArrowPierceAccessor {
    @Invoker("setPierceLevel")
    void asobibatweaks$setPierceLevel(byte pierce);

    @Invoker("isInGround")
    boolean asobibatweaks$isInGround();
}
