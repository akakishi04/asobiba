package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;

/**
 * Craft actual workstation/building pieces from approved vanilla ingredients,
 * using the Carpenter's persistent physical cargo. All transformations are
 * atomic ItemStack transactions: the output can never be minted unless every
 * input and a free destination are available in the same saved cargo snapshot.
 *
 * No virtual ledger withdrawals or free fixture-block creation are allowed.
 */
public final class VillageCarpenterCraftingService {
    private VillageCarpenterCraftingService() {}

    public static boolean isCraftedFixture(Item fixture, Block chosenPlank) {
        return fixture == Items.BARREL || fixture == Items.COMPOSTER
                || fixture == Items.SMITHING_TABLE || fixture == Items.STONECUTTER
                || fixture == Items.LECTERN || fixture == Items.BLAST_FURNACE
                || fixture == Items.CARTOGRAPHY_TABLE || fixture == Items.BREWING_STAND
                || fixture == Items.LOOM || fixture == Items.FLETCHING_TABLE
                || fixture == Items.SMOKER || fixture == Items.CAULDRON
                || fixture == Items.GRINDSTONE
                || fixture == Items.COBBLESTONE_WALL
                || fixture == Items.COBBLESTONE_STAIRS
                || fixture == VillageBridgeService.fenceForPlank(chosenPlank).asItem()
                || fixture == AsobibaRegistries.CARPENTER_WORKBENCH.get().asItem()
                || fixture == VillageSimulationEvents.stairsForPlank(chosenPlank).asItem();
    }

    public static boolean ensureFixture(
            Villager carpenter, ServerLevel level, Item fixture, Block chosenPlank,
            int capacity) {
        if (VillagerSimData.workCargoCount(carpenter,
                level.registryAccess(), capacity, fixture) >= 1) {
            return true;
        }
        // Prefer an actual existing crafted item in recognized village
        // storage before asking the builder to assemble one.
        if (VillageSimulationEvents.ensureCargoItem(
                carpenter, level, fixture, 1, capacity)) return true;

        Item plank = chosenPlank.asItem();
        Item slab = slabForPlank(chosenPlank);
        Item stair = VillageSimulationEvents.stairsForPlank(chosenPlank).asItem();

        if (fixture == Items.BARREL) {
            if (!ensureSlabs(carpenter, level, plank, slab, 2, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, plank, 6, capacity)) return false;
            return assemble(carpenter, level, capacity, new ItemStack(Items.BARREL),
                    new Ingredient(plank, 6), new Ingredient(slab, 2));
        }

        if (fixture == Items.COMPOSTER) {
            if (!ensureSlabs(carpenter, level, plank, slab, 7, capacity)) return false;
            return assemble(carpenter, level, capacity, new ItemStack(Items.COMPOSTER),
                    new Ingredient(slab, 7));
        }

        if (fixture == Items.SMITHING_TABLE) {
            // Vanilla recipe: 2 iron ingots + 4 matching wooden planks.
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.IRON_INGOT, 2, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, plank, 4, capacity)) return false;
            return assemble(carpenter, level, capacity, new ItemStack(Items.SMITHING_TABLE),
                    new Ingredient(Items.IRON_INGOT, 2), new Ingredient(plank, 4));
        }

        if (fixture == Items.STONECUTTER) {
            // Vanilla recipe: 1 iron ingot + 3 ordinary stone blocks.
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.IRON_INGOT, 1, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, Items.STONE, 3, capacity)) return false;
            return assemble(carpenter, level, capacity, new ItemStack(Items.STONECUTTER),
                    new Ingredient(Items.IRON_INGOT, 1),
                    new Ingredient(Items.STONE, 3));
        }

        // Remaining vanilla job-site fixtures. The Carpenter must physically
        // withdraw every exact ingredient; assemble commits once, and only
        // when the complete product fits in its persistent eight-slot cargo.
        if (fixture == Items.LOOM) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.STRING, 2, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, plank, 2, capacity)) return false;
            return assemble(carpenter, level, capacity, new ItemStack(Items.LOOM),
                    new Ingredient(Items.STRING, 2), new Ingredient(plank, 2));
        }
        if (fixture == Items.FLETCHING_TABLE) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.FLINT, 2, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, plank, 4, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.FLETCHING_TABLE),
                    new Ingredient(Items.FLINT, 2), new Ingredient(plank, 4));
        }
        if (fixture == Items.CARTOGRAPHY_TABLE) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.PAPER, 2, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, plank, 4, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.CARTOGRAPHY_TABLE),
                    new Ingredient(Items.PAPER, 2), new Ingredient(plank, 4));
        }
        if (fixture == Items.CAULDRON) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.IRON_INGOT, 7, capacity)) return false;
            return assemble(carpenter, level, capacity, new ItemStack(Items.CAULDRON),
                    new Ingredient(Items.IRON_INGOT, 7));
        }
        if (fixture == Items.BREWING_STAND) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.BLAZE_ROD, 1, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, Items.COBBLESTONE, 3, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.BREWING_STAND),
                    new Ingredient(Items.BLAZE_ROD, 1),
                    new Ingredient(Items.COBBLESTONE, 3));
        }
        if (fixture == Items.BLAST_FURNACE) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.FURNACE, 1, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, Items.IRON_INGOT, 5, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, Items.SMOOTH_STONE, 3, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.BLAST_FURNACE),
                    new Ingredient(Items.FURNACE, 1),
                    new Ingredient(Items.IRON_INGOT, 5),
                    new Ingredient(Items.SMOOTH_STONE, 3));
        }
        if (fixture == Items.SMOKER) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.FURNACE, 1, capacity)
                    || !VillageSimulationEvents.ensureCargoMatching(
                            carpenter, level, stack -> stack.is(ItemTags.LOGS),
                            4, capacity)) return false;
            return assemble(carpenter, level, capacity, new ItemStack(Items.SMOKER),
                    new Ingredient(Items.FURNACE, 1), new Ingredient(null, 4));
        }
        if (fixture == Items.GRINDSTONE) {
            if (!ensureSlabs(carpenter, level, Items.STONE, Items.STONE_SLAB, 1, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, Items.STICK, 2, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, plank, 2, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.GRINDSTONE),
                    new Ingredient(Items.STONE_SLAB, 1),
                    new Ingredient(Items.STICK, 2), new Ingredient(plank, 2));
        }
        if (fixture == Items.LECTERN) {
            if (!ensureSlabs(carpenter, level, plank, slab, 4, capacity)
                    || !ensureBookshelf(carpenter, level, plank, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.LECTERN),
                    new Ingredient(slab, 4), new Ingredient(Items.BOOKSHELF, 1));
        }

        if (fixture == Items.COBBLESTONE_WALL) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.COBBLESTONE, 6, capacity)) return false;
            // Vanilla cobblestone wall: six blocks -> six real walls.
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.COBBLESTONE_WALL, 6),
                    new Ingredient(Items.COBBLESTONE, 6));
        }
        if (fixture == Items.COBBLESTONE_STAIRS) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.COBBLESTONE, 6, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(Items.COBBLESTONE_STAIRS, 4),
                    new Ingredient(Items.COBBLESTONE, 6));
        }
        if (fixture == VillageBridgeService.fenceForPlank(chosenPlank).asItem()) {
            if (VillagerSimData.workCargoCount(carpenter,
                    level.registryAccess(), capacity, Items.STICK) < 2
                    && !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, Items.STICK, 2, capacity)) {
                if (!VillageSimulationEvents.ensureCargoItem(
                        carpenter, level, plank, 2, capacity)
                        || !assemble(carpenter, level, capacity,
                                new ItemStack(Items.STICK, 4),
                                new Ingredient(plank, 2))) return false;
            }
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, plank, 4, capacity)) return false;
            return assemble(carpenter, level, capacity,
                    new ItemStack(fixture, 3),
                    new Ingredient(plank, 4),
                    new Ingredient(Items.STICK, 2));
        }

        if (fixture == stair) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, plank, 6, capacity)) return false;
            // Vanilla stairs recipe: six planks -> four stairs. Any unused
            // stairs remain physical cargo for later build steps.
            return assemble(carpenter, level, capacity, new ItemStack(stair, 4),
                    new Ingredient(plank, 6));
        }

        if (fixture == AsobibaRegistries.CARPENTER_WORKBENCH.get().asItem()) {
            if (!ensureCraftingTable(carpenter, level, plank, capacity)
                    || !VillageSimulationEvents.ensureCargoMatching(
                            carpenter, level, stack -> stack.is(ItemTags.LOGS),
                            4, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, plank, 3, capacity)) return false;

            // Custom shaped recipe: 3 planks + 4 logs + 1 crafting table.
            return assemble(carpenter, level, capacity,
                    new ItemStack(fixture),
                    new Ingredient(plank, 3),
                    new Ingredient(null, 4),
                    new Ingredient(Items.CRAFTING_TABLE, 1));
        }

        return false;
    }

    private static boolean ensureBookshelf(
            Villager carpenter, ServerLevel level, Item plank, int capacity) {
        if (VillagerSimData.workCargoCount(carpenter,
                level.registryAccess(), capacity, Items.BOOKSHELF) > 0) return true;
        if (VillageSimulationEvents.ensureCargoItem(
                carpenter, level, Items.BOOKSHELF, 1, capacity)) return true;

        int books = VillagerSimData.workCargoCount(
                carpenter, level.registryAccess(), capacity, Items.BOOK);
        if (books < 3 && !VillageSimulationEvents.ensureCargoItem(
                carpenter, level, Items.BOOK, 3, capacity)) {
            if (!VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, Items.PAPER, 9, capacity)
                    || !VillageSimulationEvents.ensureCargoItem(
                            carpenter, level, Items.LEATHER, 3, capacity)
                    || !assemble(carpenter, level, capacity, new ItemStack(Items.BOOK, 3),
                            new Ingredient(Items.PAPER, 9),
                            new Ingredient(Items.LEATHER, 3))) return false;
        }

        if (!VillageSimulationEvents.ensureCargoItem(
                carpenter, level, plank, 6, capacity)) return false;
        return assemble(carpenter, level, capacity, new ItemStack(Items.BOOKSHELF),
                new Ingredient(Items.BOOK, 3), new Ingredient(plank, 6));
    }

    private static boolean ensureSlabs(
            Villager carpenter, ServerLevel level, Item plank, Item slab,
            int requested, int capacity) {
        int existing = VillagerSimData.workCargoCount(
                carpenter, level.registryAccess(), capacity, slab);
        if (existing >= requested) return true;

        if (VillageSimulationEvents.ensureCargoItem(
                carpenter, level, slab, requested, capacity)) return true;

        existing = VillagerSimData.workCargoCount(
                carpenter, level.registryAccess(), capacity, slab);
        int missing = requested - existing;
        if (missing <= 0) return true;

        int batches = (missing + 5) / 6;
        int planksNeeded = batches * 3;
        if (!VillageSimulationEvents.ensureCargoItem(
                carpenter, level, plank, planksNeeded, capacity)) return false;

        // Vanilla plank slabs: 3 planks -> 6 slabs. Do not throw away or
        // silently fabricate the surplus slabs from a partial batch.
        return assemble(carpenter, level, capacity,
                new ItemStack(slab, batches * 6), new Ingredient(plank, planksNeeded));
    }

    private static boolean ensureCraftingTable(
            Villager carpenter, ServerLevel level, Item plank, int capacity) {
        if (VillagerSimData.workCargoCount(carpenter,
                level.registryAccess(), capacity, Items.CRAFTING_TABLE) >= 1) return true;
        if (VillageSimulationEvents.ensureCargoItem(
                carpenter, level, Items.CRAFTING_TABLE, 1, capacity)) return true;
        if (!VillageSimulationEvents.ensureCargoItem(
                carpenter, level, plank, 4, capacity)) return false;
        return assemble(carpenter, level, capacity,
                new ItemStack(Items.CRAFTING_TABLE), new Ingredient(plank, 4));
    }

    /**
     * Compute a fully independent mutable cargo snapshot and publish it once.
     * Inputs are checked before mutation; no partial consume or partial
     * generated output survives a failed craft.
     */
    private static boolean assemble(
            Villager carpenter, ServerLevel level, int capacity,
            ItemStack product, Ingredient... ingredients) {
        List<ItemStack> existing = VillagerSimData.workCargo(
                carpenter, level.registryAccess(), capacity);
        List<ItemStack> next = new ArrayList<>(existing.size());
        for (ItemStack stack : existing) next.add(stack.copy());

        for (Ingredient ingredient : ingredients) {
            int available = 0;
            for (ItemStack stack : next) {
                if (ingredient.matches(stack)) available += stack.getCount();
            }
            if (available < ingredient.count()) return false;

            int remaining = ingredient.count();
            for (int i = 0; i < next.size() && remaining > 0; i++) {
                ItemStack item = next.get(i);
                if (!ingredient.matches(item)) continue;
                int amount = Math.min(remaining, item.getCount());
                item.shrink(amount);
                remaining -= amount;
                if (item.isEmpty()) next.set(i, ItemStack.EMPTY);
            }
        }

        int remainingOutput = product.getCount();
        for (ItemStack inSlot : next) {
            if (remainingOutput <= 0) break;
            if (inSlot.isEmpty() || !ItemStack.isSameItemSameComponents(inSlot, product)) {
                continue;
            }
            int space = Math.max(0, inSlot.getMaxStackSize() - inSlot.getCount());
            int moved = Math.min(space, remainingOutput);
            inSlot.grow(moved);
            remainingOutput -= moved;
        }
        for (int slot = 0; slot < next.size() && remainingOutput > 0; slot++) {
            if (!next.get(slot).isEmpty()) continue;
            int moved = Math.min(product.getMaxStackSize(), remainingOutput);
            next.set(slot, product.copyWithCount(moved));
            remainingOutput -= moved;
        }
        if (remainingOutput > 0) return false;

        VillagerSimData.setWorkCargo(carpenter, level.registryAccess(), next, capacity);
        return true;
    }

    private static Item slabForPlank(Block plank) {
        if (plank == Blocks.SPRUCE_PLANKS) return Items.SPRUCE_SLAB;
        if (plank == Blocks.BIRCH_PLANKS) return Items.BIRCH_SLAB;
        if (plank == Blocks.JUNGLE_PLANKS) return Items.JUNGLE_SLAB;
        if (plank == Blocks.ACACIA_PLANKS) return Items.ACACIA_SLAB;
        if (plank == Blocks.DARK_OAK_PLANKS) return Items.DARK_OAK_SLAB;
        if (plank == Blocks.MANGROVE_PLANKS) return Items.MANGROVE_SLAB;
        if (plank == Blocks.CHERRY_PLANKS) return Items.CHERRY_SLAB;
        return Items.OAK_SLAB;
    }

    /** A null Item denotes the allowed minecraft:logs tag family. */
    private record Ingredient(Item item, int count) {
        boolean matches(ItemStack stack) {
            return !stack.isEmpty() && (item == null
                    ? stack.is(ItemTags.LOGS) : stack.is(item));
        }
    }
}
