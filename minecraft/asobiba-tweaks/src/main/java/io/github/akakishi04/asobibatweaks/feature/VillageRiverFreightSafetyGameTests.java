package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.network.chat.Component;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Actual river Porter inventory transactions, independent of NPC travel. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageRiverFreightSafetyGameTests {
    private static final BlockPos MARK = new BlockPos(2, 2, 7);
    private VillageRiverFreightSafetyGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverPorterDoesNotExportConstructionReservations(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        reserve(f, "minecraft:cobblestone", 64);
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        assertUntouched(helper, f, "Reserved construction stock was exported");
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverCategoryStockSuppressesEquivalentImports(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        f.remote().setItem(0, new ItemStack(Items.STONE, 32));
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        assertUntouched(helper, f, "Real remote Stone must satisfy the Cobblestone category demand");
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverPickupRechecksNewConstructionReservations(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        stageUnpaidTicket(helper, f);
        reserve(f, "minecraft:cobblestone", 64);
        move(f.porter(), f.corePos());
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        assertUntouched(helper, f, "Reservation added during travel must cancel unpaid pickup");
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverPickupRechecksReplenishedDestination(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        stageUnpaidTicket(helper, f);
        f.remote().setItem(0, new ItemStack(Items.STONE, 32));
        move(f.porter(), f.corePos());
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        assertUntouched(helper, f, "Replenished remote category must cancel unpaid pickup");
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverUnknownWarehouseIsNotAnEmptyWarehouse(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        BlockPos extra = new BlockPos(13, 2, 7);
        helper.setBlock(extra, Blocks.BARREL);
        var record = f.world().data().createStorage(f.world().route().villageId(),
                helper.absolutePos(extra), "general");
        record.setValidationState("cached");
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        assertUntouched(helper, f, "An unvalidated remote store must not create phantom shortage");
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverAbsentRegisteredWarehouseDoesNotCreateDemand(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        // This registration is deliberately absent from containers(), just as
        // an unloaded warehouse is; never force-load terrain to fill the gap.
        var record = f.world().data().createStorage(f.world().route().villageId(),
                helper.absolutePos(new BlockPos(13, 2, 7)), "general");
        record.setValidationState("valid");
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        assertUntouched(helper, f, "A registered warehouse missing from the loaded snapshot must veto dispatch");
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverPaidCargoSurvivesLaterDemandChanges(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        if (VillagerSimData.workCargoCount(f.porter(), f.world().level().registryAccess(),
                16, Items.COBBLESTONE) != 32) {
            helper.fail("Fixture did not physically withdraw its paid shipment", MARK);
            return;
        }
        reserve(f, "minecraft:cobblestone", 32);
        f.remote().setItem(0, new ItemStack(Items.STONE, 64));
        move(f.porter(), helper.absolutePos(new BlockPos(1, 2, 5)));
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        if (count(f.core(), Items.COBBLESTONE) != 32
                || count(f.world().source(), Items.COBBLESTONE) != 32
                || VillagerSimData.hasWorkCargo(f.porter(), f.world().level().registryAccess(), 16)) {
            helper.fail("Fresh demand checks must never cancel or erase already paid physical cargo", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverExactReservedItemSurvivesCategorySurplus(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        f.core().setItem(1, new ItemStack(Items.STONE, 64));
        reserve(f, "minecraft:cobblestone", 64);
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        if (count(f.core(), Items.COBBLESTONE) != 64 || count(f.core(), Items.STONE) != 32
                || VillagerSimData.workCargoCount(f.porter(), f.world().level().registryAccess(),
                    16, Items.STONE) != 32) {
            helper.fail("Other category surplus must not authorize withdrawing the reserved exact item", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "river_porter")
    public static void riverCategorySurplusMovesExactNamedStack(GameTestHelper helper) {
        Fixture f = setup(helper);
        ItemStack named = new ItemStack(Items.COBBLESTONE, 32);
        named.set(DataComponents.CUSTOM_NAME, Component.literal("Paid river freight"));
        f.core().setItem(0, named.copy());
        f.core().setItem(1, new ItemStack(Items.STONE, 32));
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        var cargo = VillagerSimData.workCargo(f.porter(), f.world().level().registryAccess(), 16);
        if (count(f.core(), Items.COBBLESTONE) != 0 || count(f.core(), Items.STONE) != 32
                || cargo.stream().filter(s -> ItemStack.isSameItemSameComponents(s, named))
                    .mapToInt(ItemStack::getCount).sum() != 32) {
            helper.fail("Category aggregation must still withdraw only the genuine component-identical stack", MARK);
            return;
        }
        move(f.porter(), helper.absolutePos(new BlockPos(1, 2, 5)));
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        if (count(f.world().source(), Items.COBBLESTONE) != 32
                || !ItemStack.isSameItemSameComponents(f.world().source().getItem(0), named)
                || VillagerSimData.hasWorkCargo(f.porter(), f.world().level().registryAccess(), 16)) {
            helper.fail("Paid river cargo lost components or duplicated during dock delivery", MARK);
            return;
        }
        helper.succeed();
    }

    private static void reserve(Fixture f, String key, int amount) {
        var village = f.world().data().village(f.world().route().villageId()).orElseThrow();
        village.replaceLedger(Map.of(key, amount));
        if (!village.reserve(key, amount)) throw new IllegalStateException("Fixture reservation failed");
    }

    private static void stageUnpaidTicket(GameTestHelper helper, Fixture f) {
        // Explicitly staged movement tests the physical transaction boundary;
        // it does not claim autonomous NPC pathfinding coverage.
        move(f.porter(), f.remotePos());
        VillageRiverPorterService.handlePorter(f.porter(), f.world().level(), null);
        if (!VillagerSimData.riverHaul(f.porter()).map(h -> "pickup".equals(h.phase())).orElse(false)
                || count(f.core(), Items.COBBLESTONE) != 64) {
            throw new IllegalStateException("Fixture did not create an unpaid distant pickup ticket");
        }
    }

    private static void assertUntouched(GameTestHelper helper, Fixture f, String message) {
        if (count(f.core(), Items.COBBLESTONE) != 64
                || count(f.world().source(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(f.porter(), f.world().level().registryAccess(), 16)
                || VillagerSimData.riverHaul(f.porter()).isPresent()) {
            helper.fail(message, MARK);
            return;
        }
        helper.succeed();
    }

    private static Fixture setup(GameTestHelper helper) {
        var world = VillageRiverCargoGameTests.setup(helper);
        BlockPos core = helper.absolutePos(MARK);
        BlockPos remote = helper.absolutePos(new BlockPos(14, 2, 7));
        helper.setBlock(MARK, Blocks.BARREL);
        helper.setBlock(new BlockPos(14, 2, 7), Blocks.BARREL);
        var outpost = world.data().createWorkSite(world.route().villageId(), "outpost",
                helper.absolutePos(new BlockPos(12, 1, 2)),
                helper.absolutePos(new BlockPos(15, 4, 8)));
        outpost.setState("active");
        outpost.setPurpose("quarry");
        for (BlockPos p : new BlockPos[]{core, remote}) {
            var storage = world.data().createStorage(world.route().villageId(), p, "general");
            storage.setValidationState("valid");
        }
        Villager porter = EntityType.VILLAGER.create(world.level());
        if (porter == null) throw new IllegalStateException("Porter creation failed");
        move(porter, core);
        if (!world.level().addFreshEntity(porter)) throw new IllegalStateException("Porter spawn failed");
        VillagerSimData.setVillageId(porter, world.route().villageId());
        VillagerSimData.setDuty(porter, "porter", world.level().getGameTime());
        world.data().touch();
        return new Fixture(world, (Container)world.level().getBlockEntity(core),
                (Container)world.level().getBlockEntity(remote), core, remote, porter);
    }

    private static void move(Villager porter, BlockPos pos) {
        porter.setPos(pos.getX() + 0.5D, pos.getY() + 1.0D, pos.getZ() + 0.5D);
    }

    private static int count(Container container, Item item) {
        int total = 0;
        for (int slot = 0; slot < container.getContainerSize(); slot++) {
            ItemStack stack = container.getItem(slot);
            if (stack.is(item)) total += stack.getCount();
        }
        return total;
    }

    private record Fixture(VillageRiverCargoGameTests.Fixture world, Container core,
                           Container remote, BlockPos corePos, BlockPos remotePos, Villager porter) {}
}
