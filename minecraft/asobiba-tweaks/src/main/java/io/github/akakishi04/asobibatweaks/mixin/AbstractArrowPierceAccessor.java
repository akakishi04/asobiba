package io.github.akakishi04.asobibatweaks.mixin;

import net.minecraft.world.entity.projectile.AbstractArrow;
import it.unimi.dsi.fastutil.ints.IntOpenHashSet;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Private vanilla piercing setter for already-created arrow entities. */
@Mixin(AbstractArrow.class)
public interface AbstractArrowPierceAccessor {
    @Invoker("setPierceLevel")
    void asobibatweaks$setPierceLevel(byte pierce);

    @Accessor("inGround")
    boolean asobibatweaks$isInGround();

    /**
     * Vanilla records *all* entity collisions it processed for Piercing,
     * including armor stands and other non-LivingEntity targets. This is
     * the real capacity accounting source, unlike LivingDamageEvent.Post.
     */
    @Accessor("piercingIgnoreEntityIds")
    IntOpenHashSet asobibatweaks$getPiercingIgnoreEntityIds();
}
