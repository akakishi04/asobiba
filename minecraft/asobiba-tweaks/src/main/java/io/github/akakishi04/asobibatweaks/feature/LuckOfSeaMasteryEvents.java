package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.List;
import net.minecraft.core.component.DataComponents;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.ItemEnchantments;
import net.minecraft.world.level.storage.loot.BuiltInLootTables;
import net.minecraft.world.level.storage.loot.LootParams;
import net.minecraft.world.level.storage.loot.parameters.LootContextParamSets;
import net.minecraft.world.level.storage.loot.parameters.LootContextParams;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.ItemFishedEvent;

/**
 * Luck of the Sea mastery improves the actual chosen catch, never adding
 * independent loot items after the fishing-event transaction.
 */
public final class LuckOfSeaMasteryEvents {
    @SubscribeEvent
    public void onActualFishingCatch(ItemFishedEvent event) {
        if (event.isCanceled() || !(event.getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getDrops().isEmpty()) return;

        ItemStack rod = player.getMainHandItem().is(Items.FISHING_ROD)
                ? player.getMainHandItem() : player.getOffhandItem();
        var branch = LauncherReloadMasteryEvents.branch(rod, "minecraft:luck_of_the_sea");
        if (branch == null) return;

        ItemStack original = event.getDrops().get(0);
        if (original.isEmpty()) return;
        double progress = branch.progress();

        if (branch.choice() == 0 && !isTreasure(original)) {
            // Treasure's vanilla weight is ~5%, modified by Luck's level.
            // Reroll only a fraction of non-treasure outcomes, calibrated so
            // the relative weight increases ~10-35%, not a free extra item.
            int level = EnchantedArrowImpactEvents.level(rod, "minecraft:luck_of_the_sea");
            double estimatedBase = Math.min(0.35D, 0.05D + 0.02D * level);
            double extra = 0.10D + 0.25D * progress;
            double chance = estimatedBase * extra / (1.0D + estimatedBase * extra);
            if (player.getRandom().nextDouble() < chance) {
                ItemStack rerolled = oneTreasure(player, rod, event);
                if (!rerolled.isEmpty()) event.getDrops().set(0, rerolled);
            }
        } else if (branch.choice() == 1
                && player.getRandom().nextDouble() < 0.10D + 0.20D * progress) {
            improveOneCatch(original, player);
        }
        // Rare Catch (branch 2) is intentionally a no-op in the ordinary
        // fishing table: it has no dedicated rare regional/living category.
        // The Nether/Lava Fishing table applies this branch only where its
        // actual rare-fish entries exist.
    }

    private static ItemStack oneTreasure(ServerPlayer player, ItemStack rod,
                                         ItemFishedEvent event) {
        if (!(player.level() instanceof ServerLevel level)) return ItemStack.EMPTY;
        LootParams parameters = new LootParams.Builder(level)
                .withParameter(LootContextParams.ORIGIN, event.getHookEntity().position())
                .withParameter(LootContextParams.TOOL, rod)
                .withParameter(LootContextParams.THIS_ENTITY, event.getHookEntity())
                .withParameter(LootContextParams.ATTACKING_ENTITY, player)
                .withLuck(player.getLuck())
                .create(LootContextParamSets.FISHING);
        List<ItemStack> treasure = level.getServer().reloadableRegistries()
                .getLootTable(BuiltInLootTables.FISHING_TREASURE).getRandomItems(parameters);
        return treasure.isEmpty() ? ItemStack.EMPTY : treasure.get(0).copy();
    }

    private static boolean isTreasure(ItemStack stack) {
        return stack.is(Items.BOW) || stack.is(Items.FISHING_ROD)
                || stack.is(Items.ENCHANTED_BOOK) || stack.is(Items.NAME_TAG)
                || stack.is(Items.NAUTILUS_SHELL) || stack.is(Items.SADDLE);
    }

    private static void improveOneCatch(ItemStack stack, ServerPlayer player) {
        if (stack.is(Items.ENCHANTED_BOOK)) {
            ItemEnchantments existing = stack.getOrDefault(
                    DataComponents.STORED_ENCHANTMENTS, ItemEnchantments.EMPTY);
            var available = existing.entrySet().stream()
                    .filter(e -> e.getIntValue() < e.getKey().value().getMaxLevel())
                    .toList();
            if (available.isEmpty()) return;

            var selected = available.get(player.getRandom().nextInt(available.size()));
            ItemEnchantments.Mutable improved = new ItemEnchantments.Mutable(existing);
            improved.set(selected.getKey(), selected.getIntValue() + 1);
            stack.set(DataComponents.STORED_ENCHANTMENTS, improved.toImmutable());
        } else if (stack.isDamageableItem() && stack.isDamaged()) {
            int improvement = Math.max(1, (int)Math.ceil(stack.getMaxDamage() * 0.15D));
            stack.setDamageValue(Math.max(0, stack.getDamageValue() - improvement));
        }
    }

    /**
     * NetherFishingEvents creates its own real regional catch category:
     * rare Basalt Eels are the only valid branch-2 specialization target.
     */
    public static int adjustNetherRoll(ServerPlayer player, ItemStack rod, int ordinaryRoll) {
        var branch = LauncherReloadMasteryEvents.branch(rod, "minecraft:luck_of_the_sea");
        if (branch == null || branch.choice() != 2
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || ordinaryRoll >= 54 && ordinaryRoll < 66) return ordinaryRoll;

        double relativeExtra = 0.10D + 0.30D * branch.progress();
        double conversionChance = 0.12D * relativeExtra / (1.0D + 0.12D * relativeExtra);
        if (player.getRandom().nextDouble() < conversionChance) {
            return 54 + player.getRandom().nextInt(12);
        }
        return ordinaryRoll;
    }
}
