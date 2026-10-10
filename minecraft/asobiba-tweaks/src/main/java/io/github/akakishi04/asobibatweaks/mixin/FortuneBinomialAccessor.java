package io.github.akakishi04.asobibatweaks.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Separate crop baseline trials from additional Fortune trials without rerolls. */
@Mixin(targets = "net.minecraft.world.level.storage.loot.functions.ApplyBonusCount$BinomialWithBonusCount")
public interface FortuneBinomialAccessor {
    @Accessor("extraRounds") int asobibatweaks$extraRounds();
    @Accessor("probability") float asobibatweaks$probability();
}
