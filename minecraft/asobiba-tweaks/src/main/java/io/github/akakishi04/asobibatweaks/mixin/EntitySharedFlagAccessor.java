package io.github.akakishi04.asobibatweaks.mixin;

import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;

@Mixin(Entity.class)
public interface EntitySharedFlagAccessor {
    @Invoker("setSharedFlag")
    void asobibatweaks$setSharedFlag(int flag, boolean set);
}
