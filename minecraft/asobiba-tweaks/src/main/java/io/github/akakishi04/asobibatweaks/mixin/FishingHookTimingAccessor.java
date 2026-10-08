package io.github.akakishi04.asobibatweaks.mixin;

import net.minecraft.world.entity.projectile.FishingHook;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/**
 * Field-level read/write only: no replacement of vanilla hook ticking or
 * loot generation. Timers continue to obey vanilla bobber states.
 */
@Mixin(FishingHook.class)
public interface FishingHookTimingAccessor {
    @Accessor("timeUntilLured")
    int asobibatweaks$getWaitingTicks();

    @Accessor("timeUntilLured")
    void asobibatweaks$setWaitingTicks(int ticks);

    @Accessor("nibble")
    int asobibatweaks$getBiteWindow();

    @Accessor("nibble")
    void asobibatweaks$setBiteWindow(int ticks);
}
