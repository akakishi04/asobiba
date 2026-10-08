package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTags;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentRerollProtocol;
import io.github.akakishi04.asobibatweaks.feature.EnchantedWorkBlockSavedData;
import java.util.List;
import java.util.ArrayList;
import java.util.stream.Stream;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.stats.Stats;
import net.minecraft.advancements.CriteriaTriggers;
import net.minecraft.world.item.Items;
import net.neoforged.neoforge.common.CommonHooks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.core.IdMap;
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
import net.minecraft.world.item.enchantment.Enchantments;
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
import org.spongepowered.asm.mixin.gen.Invoker;

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

    /**
     * A normal enchanting slot accepts a maximum of one item; shift-click
     * already splits the player's arrow stack. If another inventory/menu
     * integration introduces multiple arrows into that input anyway,
     * isolate ONE physical arrow for the complete vanilla-priced operation.
     *
     * The unenchanted remainder is returned to the player inventory, with
     * overflow dropped in the world rather than lost or multiplied.
     */
    @Inject(method = "clickMenuButton", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$enchantExactlyOneArrow(
            Player actor, int buttonId, CallbackInfoReturnable<Boolean> cir) {
        if (!(actor instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || buttonId < 0 || buttonId > 2) {
            return;
        }

        ItemStack original = this.enchantSlots.getItem(0);
        if (!ExtendedEnchantingTargets.isExtendedArrowTarget(original)
                || original.getCount() <= 1) {
            return;
        }

        int lapisCost = buttonId + 1;
        int offerCost = ((EnchantmentMenu)(Object)this).costs[buttonId];
        ItemStack lapis = this.enchantSlots.getItem(1);
        boolean creative = player.hasInfiniteMaterials();
        if (!original.isEnchantable() || offerCost <= 0
                || (!creative && (lapis.getCount() < lapisCost
                        || player.experienceLevel < lapisCost
                        || player.experienceLevel < offerCost))) {
            cir.setReturnValue(false);
            return;
        }

        this.access.execute((level, pos) -> {
            List<EnchantmentInstance> selections =
                    this.asobibatweaks$invokeGetEnchantmentList(
                            level.registryAccess(), original, buttonId, offerCost);
            if (selections.isEmpty()) return;

            // Copy the exact source components before consuming either cost.
            // Original is never enchanted, so all other arrows remain ordinary.
            ItemStack single = original.copyWithCount(1);
            ItemStack remaining = original.copyWithCount(original.getCount() - 1);

            player.onEnchantmentPerformed(single, lapisCost);
            single = single.getItem().applyEnchantments(single, selections);
            if (single.isEmpty() || single.getCount() != 1) {
                // Fail closed for nonstandard Item implementations.
                return;
            }
            this.enchantSlots.setItem(0, single);
            CommonHooks.onPlayerEnchantItem(player, single, selections);
            lapis.consume(lapisCost, player);
            if (lapis.isEmpty()) this.enchantSlots.setItem(1, ItemStack.EMPTY);

            // If inventory fills partway, its mutated remainder is authoritative.
            player.getInventory().add(remaining);
            if (!remaining.isEmpty()) player.drop(remaining, false);

            player.awardStat(Stats.ENCHANT_ITEM);
            CriteriaTriggers.ENCHANTED_ITEM.trigger(player, single, lapisCost);
            this.enchantSlots.setChanged();
            this.enchantmentSeed.set(player.getEnchantmentSeed());
            ((EnchantmentMenu)(Object)this).slotsChanged(this.enchantSlots);
            level.playSound(null, pos, SoundEvents.ENCHANTMENT_TABLE_USE,
                    SoundSource.BLOCKS, 1.0F,
                    level.random.nextFloat() * 0.1F + 0.9F);
        });
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



    @org.spongepowered.asm.mixin.injection.Inject(method = "slotsChanged", at = @At("TAIL"))
    private void asobibatweaks$extendTableLevelCap(
            Container container,
            org.spongepowered.asm.mixin.injection.callback.CallbackInfo ci
    ) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || container != this.enchantSlots) {
            return;
        }

        ItemStack target = container.getItem(0);
        if (target.isEmpty() || !target.isEnchantable()) {
            return;
        }

        this.access.execute((level, pos) -> {
            ItemStack tableStack = EnchantedWorkBlockSavedData.get((net.minecraft.server.level.ServerLevel) level)
                    .peek(pos.asLong());
            if (tableStack.isEmpty()) {
                return;
            }

            Holder<Enchantment> efficiency = level.registryAccess()
                    .lookupOrThrow(Registries.ENCHANTMENT)
                    .getOrThrow(Enchantments.EFFICIENCY);
            int efficiencyLevel = EnchantmentHelper.getItemEnchantmentLevel(efficiency, tableStack);
            if (efficiencyLevel <= 0) {
                return;
            }

            int tableCap = Math.min(100, 30 + efficiencyLevel * 10);
            int virtualBookcases = tableCap / 2;
            EnchantmentMenu menu = (EnchantmentMenu)(Object)this;

            this.random.setSeed(this.enchantmentSeed.get());
            for (int slot = 0; slot < 3; slot++) {
                int selected = this.random.nextInt(8) + 1
                        + (virtualBookcases >> 1)
                        + this.random.nextInt(virtualBookcases + 1);
                int cost;
                if (slot == 0) {
                    cost = Math.max(selected / 3, 1);
                } else if (slot == 1) {
                    cost = selected * 2 / 3 + 1;
                } else {
                    cost = Math.max(selected, virtualBookcases * 2);
                }
                menu.costs[slot] = Math.min(cost, tableCap);
                menu.enchantClue[slot] = -1;
                menu.levelClue[slot] = -1;
            }

            IdMap<Holder<Enchantment>> holders = level.registryAccess()
                    .registryOrThrow(Registries.ENCHANTMENT)
                    .asHolderIdMap();

            for (int slot = 0; slot < 3; slot++) {
                if (menu.costs[slot] <= 0) continue;
                List<EnchantmentInstance> list =
                        this.asobibatweaks$invokeGetEnchantmentList(level.registryAccess(), target, slot, menu.costs[slot]);
                if (!list.isEmpty()) {
                    EnchantmentInstance clue = list.get(this.random.nextInt(list.size()));
                    menu.enchantClue[slot] = holders.getId(clue.enchantment);
                    menu.levelClue[slot] = clue.level;
                }
            }

            menu.broadcastChanges();
        });
    }


    /**
     * Fortune on the actual placed Enchanting Table changes only the
     * continuation decay between extra enchantment rolls. Vanilla candidate
     * eligibility, mutually incompatible enchantment sets and weighted
     * enchantment choices remain authoritative.
     */
    @Inject(method = "getEnchantmentList", at = @At("RETURN"), cancellable = true)
    private void asobibatweaks$tableFortuneContinuation(
            RegistryAccess registries, ItemStack target, int offerSlot,
            int enchantmentCost, CallbackInfoReturnable<List<EnchantmentInstance>> cir) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || cir.getReturnValue().isEmpty()) return;

        ItemStack table = this.access.evaluate((level, pos) -> {
            if (!(level instanceof net.minecraft.server.level.ServerLevel server)) {
                return ItemStack.EMPTY;
            }
            return EnchantedWorkBlockSavedData.get(server).peek(pos.asLong());
        }).orElse(ItemStack.EMPTY);
        if (table.isEmpty()) return;

        Holder<Enchantment> fortune = registries.lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FORTUNE);
        int level = Math.max(0, Math.min(10,
                EnchantmentHelper.getItemEnchantmentLevel(fortune, table)));
        if (level <= 0) return;

        var registry = registries.lookupOrThrow(Registries.ENCHANTMENT);
        var vanilla = registry.get(EnchantmentTags.IN_ENCHANTING_TABLE);
        if (vanilla.isEmpty()) return;
        Stream<Holder<Enchantment>> pool = vanilla.get().stream();
        if (AsobibaTweaksConfig.ENCHANTMENT_POOL_BOOKSHELF_ENABLED.getAsBoolean()
                && hasArcaneBookshelf()) {
            var arcane = registry.get(AsobibaTags.ARCANE_BOOKSHELF_POOL);
            if (arcane.isPresent()) {
                pool = Stream.concat(pool, arcane.get().stream()).distinct();
            }
        }

        List<EnchantmentInstance> possibles =
                new ArrayList<>(EnchantmentHelper.getAvailableEnchantmentResults(
                        enchantmentCost, target, pool));
        List<EnchantmentInstance> chosen = new ArrayList<>(cir.getReturnValue());
        for (EnchantmentInstance selected : chosen) {
            possibles.removeIf(candidate ->
                    candidate.enchantment.equals(selected.enchantment)
                            || !(Enchantment.areCompatible(
                                    selected.enchantment, candidate.enchantment)
                                    || ExtendedEnchantingTargets.allowsArrowPair(
                                            target, selected.enchantment, candidate.enchantment)));
        }

        double nextLevel = enchantmentCost;
        double decay = 0.50D + 0.035D * level;
        for (int roll = 0; roll < 64 && !possibles.isEmpty(); roll++) {
            if (this.random.nextInt(50) > nextLevel) break;

            long total = 0L;
            for (EnchantmentInstance candidate : possibles) {
                total += Math.max(1, candidate.enchantment.value().getWeight());
            }
            if (total <= 0) break;
            long pick = this.random.nextInt((int)Math.min(Integer.MAX_VALUE, total));
            EnchantmentInstance selected = possibles.get(0);
            for (EnchantmentInstance candidate : possibles) {
                pick -= Math.max(1, candidate.enchantment.value().getWeight());
                if (pick < 0L) {
                    selected = candidate;
                    break;
                }
            }

            chosen.add(selected);
            Holder<Enchantment> held = selected.enchantment;
            possibles.removeIf(candidate ->
                    candidate.enchantment.equals(held)
                            || !(Enchantment.areCompatible(held, candidate.enchantment)
                                    || ExtendedEnchantingTargets.allowsArrowPair(
                                            target, held, candidate.enchantment)));
            nextLevel *= decay;
        }
        if (chosen.size() > cir.getReturnValue().size()) {
            cir.setReturnValue(chosen);
        }
    }

    @Invoker("getEnchantmentList")
    protected abstract List<EnchantmentInstance> asobibatweaks$invokeGetEnchantmentList(
            RegistryAccess access,
            ItemStack itemStack,
            int slot,
            int enchantmentCost
    );

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
