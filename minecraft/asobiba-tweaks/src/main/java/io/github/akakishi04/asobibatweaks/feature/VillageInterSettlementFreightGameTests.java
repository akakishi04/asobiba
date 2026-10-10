package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Real inventory, persistent-worker and cross-village identity conservation. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageInterSettlementFreightGameTests {
    private static final BlockPos MARK = new BlockPos(8, 2, 4);
    private VillageInterSettlementFreightGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void realPorterMovesPaidStockBetweenSeparateVillageBarrels(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(f.porter(), f.level())
                || count(f.source(), Items.COBBLESTONE) != 48
                || VillagerSimData.workCargoCount(f.porter(), f.level().registryAccess(),
                        16, Items.COBBLESTONE) != 16) {
            helper.fail("Inter-village pickup did not transfer exactly 16 real blocks", MARK);
            return;
        }
        // Prove that both cargo and its destination/phase survive entity NBT.
        CompoundTag saved = f.porter().saveWithoutId(new CompoundTag());
        Villager detached = EntityType.VILLAGER.create(f.level());
        if (detached == null) {
            helper.fail("Cannot re-create detached Villager NBT object", MARK);
            return;
        }
        detached.load(saved);
        if (VillagerSimData.workCargoCount(detached, f.level().registryAccess(),
                    16, Items.COBBLESTONE) != 16
                || !"delivery".equals(detached.getPersistentData()
                        .getCompound("asobibatweaks_inter_village_freight").getString("phase"))) {
            helper.fail("Inter-village Porter shipment did not persist through NBT", MARK);
            return;
        }
        f.porter().setPos(f.targetPos().getX() + 0.5D,
                f.targetPos().getY() + 1.0D, f.targetPos().getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.COBBLESTONE) != 48
                || count(f.target(), Items.COBBLESTONE) != 16
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || f.porter().getPersistentData().contains(
                        "asobibatweaks_inter_village_freight", Tag.TAG_COMPOUND)
                || f.route().trafficScore() != 16) {
            helper.fail("Delivered resources or village ledger duplicated/disappeared", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void fullDestinationRetainsRealPorterParcelUntilSpaceReturns(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f)) {
            helper.fail("Expected real wheat transfer ticket", MARK);
            return;
        }
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        f.porter().setPos(f.targetPos().getX() + 0.5D,
                f.targetPos().getY() + 1.0D, f.targetPos().getZ() + 0.5D);
        for (int i = 0; i < f.target().getContainerSize(); i++)
            f.target().setItem(i, new ItemStack(Items.DIRT, 64));
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.WHEAT) != 48
                || count(f.target(), Items.WHEAT) != 0
                || VillagerSimData.workCargoCount(f.porter(),
                        f.level().registryAccess(), 16, Items.WHEAT) != 16) {
            helper.fail("A full destination must not consume real Porter cargo", MARK);
            return;
        }
        f.target().setItem(26, ItemStack.EMPTY);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.target(), Items.WHEAT) != 16
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)) {
            helper.fail("A recovered destination must receive the exact held wheat", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void removedSourceStockCancelsUnpaidTransfer(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        if (!start(f)) {
            helper.fail("Expected cargo reservation from real source", MARK);
            return;
        }
        f.source().setItem(0, ItemStack.EMPTY);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.target(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || f.porter().getPersistentData().contains(
                        "asobibatweaks_inter_village_freight", Tag.TAG_COMPOUND)) {
            helper.fail("Unpaid cross-village cargo was created from absent stock", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void splitRealStockStillPaysExactParcel(GameTestHelper helper) {
        Fixture f = setup(helper);
        for (int i = 0; i < 8; i++)
            f.source().setItem(i, new ItemStack(Items.COBBLESTONE, 8));
        if (!start(f)) {
            helper.fail("A genuine aggregate of 64 blocks across stacks should fund a ticket", MARK);
            return;
        }
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.COBBLESTONE) != 48
                || VillagerSimData.workCargoCount(f.porter(),
                        f.level().registryAccess(), 16, Items.COBBLESTONE) != 16) {
            helper.fail("Split inventory failed to fund exactly one physical parcel", MARK);
            return;
        }
        f.porter().setPos(f.targetPos().getX() + 0.5D,
                f.targetPos().getY() + 1.0D, f.targetPos().getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.COBBLESTONE) != 48
                || count(f.target(), Items.COBBLESTONE) != 16
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)) {
            helper.fail("Multiple physical source stacks did not conserve real inventory", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void sameItemWithDifferentComponentsIsNotSwapped(GameTestHelper helper) {
        Fixture f = setup(helper);
        ItemStack named = new ItemStack(Items.COBBLESTONE, 64);
        named.set(DataComponents.CUSTOM_NAME, Component.literal("Do not trade this stack"));
        f.source().setItem(0, named);
        f.source().setItem(1, new ItemStack(Items.COBBLESTONE, 64));
        if (!VillageInterSettlementFreightService.assign(f.porter(), f.level(),
                    f.route().id(), f.origin(), f.destination(),
                    f.sourcePos(), f.targetPos(), f.source().getItem(1), 16)) {
            helper.fail("Cannot reserve component-identical ordinary stack", MARK);
            return;
        }
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (f.source().getItem(0).getCount() != 64
                || f.source().getItem(0).get(DataComponents.CUSTOM_NAME) == null
                || f.source().getItem(1).getCount() != 48) {
            helper.fail("Exact-stack shipment illegally consumed customized goods", MARK);
            return;
        }
        f.porter().setPos(f.targetPos().getX() + 0.5D,
                f.targetPos().getY() + 1.0D, f.targetPos().getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.target(), Items.COBBLESTONE) != 16
                || f.target().getItem(0).get(DataComponents.CUSTOM_NAME) != null
                || f.source().getItem(0).getCount() != 64) {
            helper.fail("Inter-village ItemStack components were silently replaced", MARK);
            return;
        }
        helper.succeed();
    }

    /** Genuinely different items satisfying the same material category prevent import churn. */
    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void stoneSupplyCategoryBlocksRedundantCobbleExport(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        f.source().setItem(1, new ItemStack(Items.COBBLESTONE, 64));
        VillageSavedData data = VillageSavedData.get(f.level());
        var origin = data.village(f.origin()).orElseThrow();
        var destination = data.village(f.destination()).orElseThrow();
        var source = VillageInterSettlementFreightService.categoryInventory(
                VillageStorageService.containers(f.origin(), f.level()));
        var target = VillageInterSettlementFreightService.categoryInventory(
                VillageStorageService.containers(f.destination(), f.level()));
        if (!VillageInterSettlementFreightService.categoryTradeEligible(
                origin, destination, source, target, f.source().getItem(0))) {
            helper.fail("Actual source surplus to empty village should be exportable", MARK);
            return;
        }
        f.target().setItem(0, new ItemStack(Items.STONE, 64));
        target = VillageInterSettlementFreightService.categoryInventory(
                VillageStorageService.containers(f.destination(), f.level()));
        if (VillageInterSettlementFreightService.categoryTradeEligible(
                origin, destination, source, target, f.source().getItem(0))
                || count(f.source(), Items.COBBLESTONE) != 128
                || count(f.target(), Items.STONE) != 64) {
            helper.fail("A village already stocked with stone must not import redundant cobble", MARK);
            return;
        }
        helper.succeed();
    }

    /** Construction reservations reduce real category surplus before logistics planning. */
    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void reservedConstructionMaterialRemainsAtHome(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        f.source().setItem(1, new ItemStack(Items.COBBLESTONE, 64));
        VillageSavedData data = VillageSavedData.get(f.level());
        var village = data.village(f.origin()).orElseThrow();
        var other = data.village(f.destination()).orElseThrow();
        var from = VillageInterSettlementFreightService.categoryInventory(
                VillageStorageService.containers(f.origin(), f.level()));
        var to = VillageInterSettlementFreightService.categoryInventory(
                VillageStorageService.containers(f.destination(), f.level()));
        if (!VillageInterSettlementFreightService.categoryTradeEligible(
                village, other, from, to, f.source().getItem(0))) {
            helper.fail("Unreserved real surplus should pass source reserve gate", MARK);
            return;
        }
        village.replaceLedger(java.util.Map.of("minecraft:cobblestone", 128));
        if (!village.reserve("minecraft:cobblestone", 32)
                || VillageInterSettlementFreightService.categoryTradeEligible(
                    village, other, from, to, f.source().getItem(0))
                || count(f.source(), Items.COBBLESTONE) != 128) {
            helper.fail("Village project reserved stone was wrongly marked exportable", MARK);
            return;
        }
        helper.succeed();
    }

    /** A closed genuine road reverses a physically carried parcel, never mints it. */
    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void closedTradeRoadReturnsPaidParcelToItsRealOrigin(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(
                f.porter(), f.level())
                || count(f.source(), Items.COBBLESTONE) != 48
                || VillagerSimData.workCargoCount(
                        f.porter(), f.level().registryAccess(), 16, Items.COBBLESTONE) != 16) {
            helper.fail("Real source inventory was not charged for outgoing freight", MARK);
            return;
        }
        f.route().setState("suspended");
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.COBBLESTONE) != 64
                || count(f.target(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0) {
            helper.fail("Suspended road did not return exact real freight without a fake delivery", MARK);
            return;
        }
        helper.succeed();
    }

    /** The original returning cargo is retained when its home warehouse is full. */
    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void fullReturnWarehouseKeepsPhysicalPaidParcel(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(
                f.porter(), f.level())) {
            helper.fail("Physical shipment setup failed", MARK);
            return;
        }
        // Another worker/player can refill the original warehouse while our
        // real 16 items are still carried. Never delete that held parcel.
        for (int i = 0; i < f.source().getContainerSize(); i++)
            f.source().setItem(i, new ItemStack(Items.DIRT, 64));
        f.route().setState("inactive");
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (VillagerSimData.workCargoCount(f.porter(), f.level().registryAccess(),
                    16, Items.WHEAT) != 16
                || !VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || count(f.target(), Items.WHEAT) != 0) {
            helper.fail("Full origin store deleted returned physical cargo", MARK);
            return;
        }
        f.source().setItem(26, ItemStack.EMPTY);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.WHEAT) != 16
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())) {
            helper.fail("Recovered origin capacity did not receive the exact held parcel", MARK);
            return;
        }
        helper.succeed();
    }

    /** Loaded missing receivers trigger an actual return; missing unpaid stock does not. */
    @GameTest(template = "empty16x6x9", batch = "village_trade")
    public static void destroyedReceivingBarrelNeverStrandsPorterCargo(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(
                f.porter(), f.level())) {
            helper.fail("Could not pay original freight parcel", MARK);
            return;
        }
        f.level().setBlock(f.targetPos(), Blocks.STONE.defaultBlockState(),
                net.minecraft.world.level.block.Block.UPDATE_ALL);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (!f.level().getBlockState(f.targetPos()).is(Blocks.STONE)
                || count(f.source(), Items.COBBLESTONE) != 64
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0) {
            helper.fail("A destroyed destination dropped or manufactured real carried freight",
                    MARK);
            return;
        }
        helper.succeed();
    }


    /** A paid returned parcel may enter a genuine spare origin warehouse. */
    @GameTest(template = "empty16x6x9", batch = "trade_return_reroute")
    public static void fullOriginUsesPhysicallyRegisteredAlternateWarehouse(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(
                f.porter(), f.level())) {
            helper.fail("Could not physically pick up replacement-store shipment", MARK);
            return;
        }
        // Simulate the original container being completely refilled by others.
        for (int i = 0; i < f.source().getContainerSize(); i++)
            f.source().setItem(i, new ItemStack(Items.DIRT, 64));
        BlockPos alternatePos = helper.absolutePos(new BlockPos(4, 1, 4));
        Container alternate = alternate(f, alternatePos, f.origin());
        f.route().setState("suspended");
        f.porter().setPos(alternatePos.getX() + 0.5D,
                alternatePos.getY() + 1.0D, alternatePos.getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(alternate, Items.WHEAT) != 16
                || count(f.target(), Items.WHEAT) != 0
                || VillagerSimData.hasWorkCargo(
                    f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0) {
            helper.fail("Returned paid cargo did not reach alternate real origin storage", MARK);
            return;
        }
        helper.succeed();
    }

    /** A removed source must not permanently strand already carried items. */
    @GameTest(template = "empty16x6x9", batch = "trade_return_reroute")
    public static void destroyedOriginReturnsPaidCargoToReplacement(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(
                f.porter(), f.level())) {
            helper.fail("Could not physically load parcel before destroying source", MARK);
            return;
        }
        BlockPos alternatePos = helper.absolutePos(new BlockPos(4, 1, 4));
        Container alternate = alternate(f, alternatePos, f.origin());
        f.level().setBlock(f.sourcePos(), Blocks.STONE.defaultBlockState(),
                net.minecraft.world.level.block.Block.UPDATE_ALL);
        f.route().setState("suspended");
        f.porter().setPos(alternatePos.getX() + 0.5D,
                alternatePos.getY() + 1.0D, alternatePos.getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (!f.level().getBlockState(f.sourcePos()).is(Blocks.STONE)
                || count(alternate, Items.COBBLESTONE) != 16
                || count(f.target(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(
                    f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0) {
            helper.fail("Lost origin created or deleted freight instead of returning real cargo", MARK);
            return;
        }
        helper.succeed();
    }

    /** A nearby barrel owned by ANOTHER village is not a valid refund sink. */
    @GameTest(template = "empty16x6x9", batch = "trade_return_reroute")
    public static void foreignWarehouseNeverReceivesOriginFreight(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(
                f.porter(), f.level())) {
            helper.fail("Could not pay the foreign-storage isolation shipment", MARK);
            return;
        }
        for (int i = 0; i < f.source().getContainerSize(); i++)
            f.source().setItem(i, new ItemStack(Items.DIRT, 64));
        BlockPos wrongPos = helper.absolutePos(new BlockPos(4, 1, 4));
        Container wrong = alternate(f, wrongPos, f.destination());
        f.route().setState("inactive");
        f.porter().setPos(wrongPos.getX() + 0.5D,
                wrongPos.getY() + 1.0D, wrongPos.getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(wrong, Items.WHEAT) != 0
                || VillagerSimData.workCargoCount(
                    f.porter(), f.level().registryAccess(), 16, Items.WHEAT) != 16
                || !VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0) {
            helper.fail("Foreign village wrongly accepted real origin return goods", MARK);
            return;
        }
        helper.succeed();
    }

    /** Recipient replacement is persisted separately from the shared road endpoint. */
    @GameTest(template = "empty16x6x9", batch = "trade_delivery_reroute")
    public static void destroyedReceiverReroutesExactNamedCargoAfterReload(GameTestHelper helper) {
        Fixture f = setup(helper);
        ItemStack named = new ItemStack(Items.COBBLESTONE, 64);
        named.set(DataComponents.CUSTOM_NAME, Component.literal("Paid recipient parcel"));
        f.source().setItem(0, named);
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(f.porter(), f.level())) {
            helper.fail("Cannot stage real named recipient parcel", MARK);
            return;
        }
        BlockPos replacementPos = helper.absolutePos(new BlockPos(12, 1, 6));
        Container replacement = alternate(f, replacementPos, f.destination());
        f.level().setBlock(f.targetPos(), Blocks.STONE.defaultBlockState(), 3);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        CompoundTag ticket = f.porter().getPersistentData()
                .getCompound("asobibatweaks_inter_village_freight");
        if (!"delivery".equals(ticket.getString("phase"))
                || ticket.getLong("delivery_target") != replacementPos.asLong()
                || ticket.getLong("target") != f.targetPos().asLong()
                || !f.route().to().equals(f.targetPos())
                || count(replacement, Items.COBBLESTONE) != 0
                || count(f.source(), Items.COBBLESTONE) != 48
                || VillagerSimData.workCargoCount(f.porter(), f.level().registryAccess(),
                    16, Items.COBBLESTONE) != 16) {
            helper.fail("Replacement must reserve an exact paid parcel before physical travel", MARK);
            return;
        }
        Villager restored = EntityType.VILLAGER.create(f.level());
        if (restored == null) throw new IllegalStateException("Cannot restore freight worker");
        restored.load(f.porter().saveWithoutId(new CompoundTag()));
        f.porter().discard();
        if (restored.getPersistentData().getCompound("asobibatweaks_inter_village_freight")
                .getLong("delivery_target") != replacementPos.asLong()) {
            helper.fail("Recipient replacement did not survive actual entity NBT", MARK);
            return;
        }
        restored.setPos(replacementPos.getX() + 0.5D,
                replacementPos.getY() + 1.0D, replacementPos.getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(restored, f.level());
        VillageInterSettlementFreightService.handlePorter(restored, f.level());
        if (count(replacement, Items.COBBLESTONE) != 16
                || !ItemStack.isSameItemSameComponents(replacement.getItem(0), named)
                || count(f.source(), Items.COBBLESTONE) != 48
                || VillagerSimData.hasWorkCargo(restored, f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(restored)
                || f.route().trafficScore() != 16
                || !f.level().getBlockState(f.targetPos()).is(Blocks.STONE)) {
            helper.fail("Reloaded replacement delivery lost components or duplicated real stock", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "trade_delivery_reroute")
    public static void fullReceiverUsesOnlyItsOwnRegisteredSpare(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(f.porter(), f.level())) {
            helper.fail("Cannot stage full receiver parcel", MARK);
            return;
        }
        for (int i = 0; i < f.target().getContainerSize(); i++)
            f.target().setItem(i, new ItemStack(Items.DIRT, 64));
        BlockPos foreignPos = helper.absolutePos(new BlockPos(12, 1, 5));
        Container foreign = alternate(f, foreignPos, f.origin());
        BlockPos replacementPos = helper.absolutePos(new BlockPos(12, 1, 6));
        Container replacement = alternate(f, replacementPos, f.destination());
        f.porter().setPos(replacementPos.getX() + 0.5D,
                replacementPos.getY() + 1.0D, replacementPos.getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(replacement, Items.WHEAT) != 16 || count(foreign, Items.WHEAT) != 0
                || count(f.target(), Items.WHEAT) != 0 || count(f.source(), Items.WHEAT) != 48
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 16) {
            helper.fail("Full receiver rerouting crossed village ownership or lost physical stock", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "trade_delivery_reroute")
    public static void foreignOrInvalidReceiverNeverAcceptsHeldFreight(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(f.porter(), f.level())) {
            helper.fail("Cannot stage receiver ownership parcel", MARK);
            return;
        }
        for (int i = 0; i < f.target().getContainerSize(); i++)
            f.target().setItem(i, new ItemStack(Items.DIRT, 64));
        BlockPos foreignPos = helper.absolutePos(new BlockPos(12, 1, 5));
        Container foreign = alternate(f, foreignPos, f.origin());
        BlockPos invalidPos = helper.absolutePos(new BlockPos(12, 1, 6));
        Container invalid = alternate(f, invalidPos, f.destination());
        VillageSavedData.get(f.level()).storageAt(f.destination(), invalidPos)
                .orElseThrow().setValidationState("unknown");
        f.porter().setPos(f.targetPos().getX() + 0.5D,
                f.targetPos().getY() + 1.0D, f.targetPos().getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(foreign, Items.WHEAT) != 0 || count(invalid, Items.WHEAT) != 0
                || count(f.source(), Items.WHEAT) != 48
                || VillagerSimData.workCargoCount(f.porter(), f.level().registryAccess(),
                    16, Items.WHEAT) != 16
                || !VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0) {
            helper.fail("Foreign or invalid receiver consumed the conserved waiting parcel", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "trade_delivery_reroute")
    public static void canceledRoadOverridesPersistedRecipientReplacement(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(f.porter(), f.level())) {
            helper.fail("Cannot stage route cancellation parcel", MARK);
            return;
        }
        BlockPos replacementPos = helper.absolutePos(new BlockPos(12, 1, 6));
        Container replacement = alternate(f, replacementPos, f.destination());
        f.level().setBlock(f.targetPos(), Blocks.STONE.defaultBlockState(), 3);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        f.route().setState("suspended");
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(replacement, Items.WHEAT) != 0 || count(f.source(), Items.WHEAT) != 64
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0) {
            helper.fail("A replacement receiver bypassed real route cancellation", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "trade_delivery_reroute")
    public static void partialReceiptReroutesOnlyRemainingPhysicalCargo(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(f.porter(), f.level())) {
            helper.fail("Cannot stage partial receiver parcel", MARK);
            return;
        }
        for (int i = 0; i < f.target().getContainerSize(); i++)
            f.target().setItem(i, new ItemStack(Items.DIRT, 64));
        f.target().setItem(0, new ItemStack(Items.WHEAT, 60));
        f.porter().setPos(f.targetPos().getX() + 0.5D,
                f.targetPos().getY() + 1.0D, f.targetPos().getZ() + 0.5D);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.target(), Items.WHEAT) != 64
                || VillagerSimData.workCargoCount(f.porter(), f.level().registryAccess(),
                    16, Items.WHEAT) != 12 || f.route().trafficScore() != 4) {
            helper.fail("Partial receiver must accept only four actual carried items", MARK);
            return;
        }
        BlockPos replacementPos = helper.absolutePos(new BlockPos(12, 1, 6));
        Container replacement = alternate(f, replacementPos, f.destination());
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(replacement, Items.WHEAT) != 12 || count(f.target(), Items.WHEAT) != 64
                || count(f.source(), Items.WHEAT) != 48
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 16) {
            helper.fail("Replacement replay duplicated the already receipted part of a parcel", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "trade_delivery_reroute")
    public static void removedReplacementIsRevalidatedBeforeDelivery(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        if (!start(f) || !VillageInterSettlementFreightService.handlePorter(f.porter(), f.level())) {
            helper.fail("Cannot stage replacement revalidation parcel", MARK);
            return;
        }
        BlockPos replacementPos = helper.absolutePos(new BlockPos(12, 1, 6));
        alternate(f, replacementPos, f.destination());
        f.level().setBlock(f.targetPos(), Blocks.STONE.defaultBlockState(), 3);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        f.level().setBlock(replacementPos, Blocks.GLASS.defaultBlockState(), 3);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.WHEAT) != 64
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())
                || f.route().trafficScore() != 0
                || !f.level().getBlockState(replacementPos).is(Blocks.GLASS)) {
            helper.fail("Removed replacement was not physically revalidated before cargo debit", MARK);
            return;
        }
        helper.succeed();
    }

    private static Container alternate(Fixture f, BlockPos pos, UUID owner) {
        f.level().setBlock(pos.below(), Blocks.STONE.defaultBlockState(),
                net.minecraft.world.level.block.Block.UPDATE_ALL);
        f.level().setBlock(pos, Blocks.BARREL.defaultBlockState(),
                net.minecraft.world.level.block.Block.UPDATE_ALL);
        var data = VillageSavedData.get(f.level());
        var record = data.createStorage(owner, pos, "general");
        record.setValidationState("valid");
        data.touch();
        if (!(f.level().getBlockEntity(pos) instanceof Container container))
            throw new IllegalStateException("Missing real alternate Barrel");
        return container;
    }

    private static boolean start(Fixture f) {
        return VillageInterSettlementFreightService.assign(f.porter(), f.level(),
                f.route().id(), f.origin(), f.destination(), f.sourcePos(),
                f.targetPos(), f.source().getItem(0), 16);
    }

    private static Fixture setup(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();
        BlockPos from = helper.absolutePos(new BlockPos(2, 1, 4));
        BlockPos to = helper.absolutePos(new BlockPos(12, 1, 4));
        helper.setBlock(new BlockPos(2, 0, 4), Blocks.STONE);
        helper.setBlock(new BlockPos(12, 0, 4), Blocks.STONE);
        helper.setBlock(new BlockPos(2, 1, 4), Blocks.BARREL);
        helper.setBlock(new BlockPos(12, 1, 4), Blocks.BARREL);
        VillageSavedData data = VillageSavedData.get(level);
        var origin = data.createVillage(from, level.getGameTime());
        var destination = data.createVillage(to, level.getGameTime());
        var fromRecord = data.createStorage(origin.id(), from, "general");
        fromRecord.setValidationState("valid");
        var toRecord = data.createStorage(destination.id(), to, "general");
        toRecord.setValidationState("valid");
        var route = data.createRoute(origin.id(), "inter_village_trade", from, to);
        data.setRouteWaypoints(route.id(), List.of(from, to));
        route.setState("active");
        data.touch();
        Villager porter = EntityType.VILLAGER.create(level);
        if (porter == null) throw new IllegalStateException("Missing test villager");
        porter.setPos(from.getX() + 0.5D, from.getY() + 1.0D, from.getZ() + 0.5D);
        porter.setNoAi(true);
        if (!level.addFreshEntity(porter)) throw new IllegalStateException("Villager spawn failed");
        VillagerSimData.setVillageId(porter, origin.id());
        VillagerSimData.setDuty(porter, "porter", level.getGameTime());
        if (!(level.getBlockEntity(from) instanceof Container source)
                || !(level.getBlockEntity(to) instanceof Container target))
            throw new IllegalStateException("Physical test Barrels not registered");
        return new Fixture(level, origin.id(), destination.id(),
                from, to, source, target, porter, route);
    }

    private static int count(Container container, net.minecraft.world.item.Item item) {
        int sum = 0;
        for (int i = 0; i < container.getContainerSize(); i++)
            if (container.getItem(i).is(item)) sum += container.getItem(i).getCount();
        return sum;
    }

    private record Fixture(ServerLevel level, UUID origin, UUID destination,
                           BlockPos sourcePos, BlockPos targetPos,
                           Container source, Container target, Villager porter,
                           VillageSavedData.RouteRecord route) {}
}
