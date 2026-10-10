package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import io.github.akakishi04.asobibatweaks.feature.FortuneMasteryService;
import net.minecraft.core.Holder;
import net.minecraft.util.RandomSource;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.level.storage.loot.LootContext;
import net.minecraft.world.level.storage.loot.functions.ApplyBonusCount;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;

@Mixin(ApplyBonusCount.class)
public abstract class FortuneLootBonusMixin {
    @Shadow @Final private Holder<Enchantment> enchantment;

    @WrapOperation(method = "run", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/level/storage/loot/functions/ApplyBonusCount$Formula;calculateNewCount(Lnet/minecraft/util/RandomSource;II)I"))
    private int asobibatweaks$onlyRealFortuneBonus(@Coerce Object formula,
            RandomSource random, int count, int enchantmentLevel, Operation<Integer> original,
            ItemStack stack, LootContext context) {
        if (!enchantment.is(Enchantments.FORTUNE) || enchantmentLevel <= 0
                || !FortuneMasteryService.hasBranch(context))
            return original.call(formula, random, count, enchantmentLevel);
        int baseline = count;
        int generated;
        if (formula instanceof FortuneBinomialAccessor binomial) {
            // Exact vanilla trial order/count/probability. Baseline crop trials
            // are first; only subsequent enchantment-added successes are bonus.
            generated = count;
            int extra = binomial.asobibatweaks$extraRounds();
            for (int i = 0; i < enchantmentLevel + extra; i++) {
                if (random.nextFloat() < binomial.asobibatweaks$probability()) {
                    generated++;
                    if (i < extra) baseline++;
                }
            }
        } else {
            // Vanilla OreDrops and UniformBonusCount return exactly count at L0.
            generated = original.call(formula, random, count, enchantmentLevel);
        }
        return FortuneMasteryService.adjust(baseline, generated, context);
    }
}
