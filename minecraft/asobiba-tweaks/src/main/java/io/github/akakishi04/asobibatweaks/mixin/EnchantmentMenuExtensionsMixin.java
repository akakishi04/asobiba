package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTags;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentRerollProtocol;
import java.util.List;
import java.util.stream.Stream;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.EnchantmentTags;
import net.minecraft.util.RandomSource;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ContainerLevelAccess;
import net.minecraft.world.inventory.DataSlot;
import net.minecraft.world.inventory.EnchantmentMenu;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.EnchantmentInstance;
import net.minecraft.world.level.block.EnchantingTableBlock;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(EnchantmentMenu.class)
public abstract class EnchantmentMenuExtensionsMixin {
    @Shadow @Final
    private Container enchantSlots;

    @Shadow @Final
    private ContainerLevelAccess access;

    @Shadow @Final
    private RandomSource random;

    @Shadow @Final
    private DataSlot enchantmentSeed;

    @Inject(method = "clickMenuButton", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$reroll(Player player, int buttonId, CallbackInfoReturnable<Boolean> cir) {
        if (buttonId != EnchantmentRerollProtocol.BUTTON_ID) {
            return;
        }
        if (!AsobibaTweaksConfig.ENCHANTMENT_REROLL_ENABLED.getAsBoolean()) {
            cir.setReturnValue(false);
            return;
        }

        ItemStack target = this.enchantSlots.getItem(0);
        int cost = AsobibaTweaksConfig.ENCHANTMENT_REROLL_LEVEL_COST.getAsInt();
        if (target.isEmpty() || !target.isEnchantable()) {
            cir.setReturnValue(false);
            return;
        }
        if (!player.hasInfiniteMaterials() && player.experienceLevel < cost) {
            cir.setReturnValue(false);
            return;
        }

        player.onEnchantmentPerformed(target, player.hasInfiniteMaterials() ? 0 : cost);
        this.enchantmentSeed.set(player.getEnchantmentSeed());
        ((EnchantmentMenu)(Object)this).slotsChanged(this.enchantSlots);
        this.access.execute((level, pos) ->
                level.playSound(null, pos, SoundEvents.ENCHANTMENT_TABLE_USE,
                        SoundSource.BLOCKS, 0.75F, 1.15F + level.random.nextFloat() * 0.1F));
        cir.setReturnValue(true);
    }

    @Inject(method = "getEnchantmentList", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$arcanePool(
            RegistryAccess registryAccess,
            ItemStack itemStack,
            int slot,
            int enchantmentCost,
            CallbackInfoReturnable<List<EnchantmentInstance>> cir
    ) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_POOL_BOOKSHELF_ENABLED.getAsBoolean()
                || !hasArcaneBookshelf()) {
            return;
        }

        var registry = registryAccess.lookupOrThrow(Registries.ENCHANTMENT);
        var vanilla = registry.get(EnchantmentTags.IN_ENCHANTING_TABLE);
        var arcane = registry.get(AsobibaTags.ARCANE_BOOKSHELF_POOL);
        if (vanilla.isEmpty() || arcane.isEmpty()) {
            return;
        }

        this.random.setSeed(this.enchantmentSeed.get() + slot);
        Stream<Holder<Enchantment>> candidates = Stream.concat(
                vanilla.get().stream(),
                arcane.get().stream()
        ).distinct();

        List<EnchantmentInstance> list =
                EnchantmentHelper.selectEnchantment(this.random, itemStack, enchantmentCost, candidates);

        if (itemStack.is(net.minecraft.world.item.Items.BOOK) && list.size() > 1) {
            list.remove(this.random.nextInt(list.size()));
        }
        cir.setReturnValue(list);
    }


    private boolean hasArcaneBookshelf() {
        return this.access.evaluate((level, pos) -> {
            for (BlockPos offset : EnchantingTableBlock.BOOKSHELF_OFFSETS) {
                if (EnchantingTableBlock.isValidBookShelf(level, pos, offset)
                        && level.getBlockState(pos.offset(offset)).is(AsobibaRegistries.ARCANE_BOOKSHELF.get())) {
                    return true;
                }
            }
            return false;
        }).orElse(false);
    }
}
