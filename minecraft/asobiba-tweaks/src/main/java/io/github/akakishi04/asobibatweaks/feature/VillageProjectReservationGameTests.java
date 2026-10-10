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

/** Live ProjectRecord demand drives both real freight and daily prices. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageProjectReservationGameTests {
    private static final BlockPos MARK = new BlockPos(8, 2, 4);

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void activeProjectBillsAffectMarketWithoutConsumingPhysicalFood(GameTestHelper helper) {
        Fixture f = setup(helper);
        var data = VillageSavedData.get(f.level());
        var village = data.village(f.origin()).orElseThrow();
        f.source().setItem(0, new ItemStack(Items.WHEAT, 64));
        VillageEconomyService.refreshVillage(f.level(), f.origin());
        int sustainable = village.sustainablePopulation();
        int viability = village.settlementViability();
        var project = data.createProject(f.origin(), "construction", 20, f.sourcePos());
        project.setReservation("minecraft:wheat", 64);
        VillageEconomyService.refreshVillage(f.level(), f.origin());
        if (village.marketPermille("food") != 1600
                || village.ledgerCount("minecraft:wheat") != 64
                || count(f.source(), Items.WHEAT) != 64
                || village.sustainablePopulation() != sustainable
                || village.settlementViability() != viability) {
            helper.fail("Reserved real food must affect price, not physical demographic stock", MARK);
            return;
        }
        project.setPhase("cancelled");
        VillageEconomyService.refreshVillage(f.level(), f.origin());
        if (village.marketPermille("food") != 800) {
            helper.fail("Cancelled project bill must release market scarcity", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void newProjectBillStopsAlreadyPlannedUnpaidFreight(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        if (!start(f)) { helper.fail("Expected initial unreserved ticket", MARK); return; }
        var data = VillageSavedData.get(f.level());
        var project = data.createProject(f.origin(), "repair", 20, f.sourcePos());
        project.setReservation("minecraft:cobblestone", 64);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.source(), Items.COBBLESTONE) != 64
                || VillagerSimData.hasWorkCargo(f.porter(), f.level().registryAccess(), 16)
                || VillageInterSettlementFreightService.hasActiveTicket(f.porter())) {
            helper.fail("New active repair bill did not cancel unpaid withdrawal safely", MARK);
            return;
        }
        project.setPhase("complete");
        if (!start(f)) { helper.fail("Completed bill still blocks real stock", MARK); return; }
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        project.setPhase("planned");
        project.setReservation("minecraft:cobblestone", 64);
        f.porter().setPos(f.targetPos().getX() + 0.5, f.targetPos().getY() + 1, f.targetPos().getZ() + 0.5);
        VillageInterSettlementFreightService.handlePorter(f.porter(), f.level());
        if (count(f.target(), Items.COBBLESTONE) != 16 || count(f.source(), Items.COBBLESTONE) != 48) {
            helper.fail("Later reservations must not delete paid cargo", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void exactReservedItemCannotHideBehindOtherCategorySurplus(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        f.source().setItem(1, new ItemStack(Items.STONE, 64));
        var data = VillageSavedData.get(f.level());
        var project = data.createProject(f.origin(), "repair", 20, f.sourcePos());
        project.setReservation("minecraft:cobblestone", 64);
        if (start(f) || count(f.source(), Items.COBBLESTONE) != 64) {
            helper.fail("Other stone surplus authorized exporting exact reserved cobblestone", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void boundedProjectSnapshotPausesPricingAndFreight(GameTestHelper helper) {
        Fixture f = setup(helper);
        var data = VillageSavedData.get(f.level());
        var village = data.village(f.origin()).orElseThrow();
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        village.setMarketPermille("stone", 1150);
        for (int i = 0; i <= VillageResourceReservations.MAX_PROJECTS; i++)
            data.createProject(f.origin(), "repair", 20, f.sourcePos());
        VillageEconomyService.refreshVillage(f.level(), f.origin());
        if (VillageResourceReservations.capture(data, village).complete()
                || start(f) || village.marketPermille("stone") != 1150
                || count(f.source(), Items.COBBLESTONE) != 64) {
            helper.fail("Over-budget project snapshot must fail closed without stock or price mutations", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void missingWarehouseNeverCreatesMarketScarcity(GameTestHelper helper) {
        Fixture f = setup(helper);
        var data = VillageSavedData.get(f.level());
        var village = data.village(f.origin()).orElseThrow();
        village.setMarketPermille("stone", 1150);
        data.createStorage(f.origin(), f.sourcePos().above(3), "general");
        VillageEconomyService.refreshVillage(f.level(), f.origin());
        if (village.marketPermille("stone") != 1150) {
            helper.fail("Incomplete recognized warehouses must retain verified market state", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void pausedProjectTagsStayReservedAndPersist(GameTestHelper helper) {
        Fixture f = setup(helper);
        var data = VillageSavedData.get(f.level());
        var project = data.createProject(f.origin(), "construction", 20, f.sourcePos());
        project.setPhase("paused");
        project.setReservation("tag:minecraft:planks", 60);
        project.setReservation("minecraft:oak_planks", 4);
        var restored = VillageSavedData.load(data.save(new CompoundTag(), f.level().registryAccess()),
                f.level().registryAccess());
        var snapshot = VillageResourceReservations.capture(restored, restored.village(f.origin()).orElseThrow());
        if (!snapshot.complete() || snapshot.categoryCount("wood") != 64
                || snapshot.itemCount(new ItemStack(Items.OAK_PLANKS)) != 64
                || !restored.village(f.origin()).orElseThrow().reservedCounts().isEmpty()) {
            helper.fail("Read-only snapshot lost paused/tag bills or rewrote legacy reserves", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void actualRepairBillBlocksRiverPorterPickup(GameTestHelper helper) {
        var world = VillageRiverCargoGameTests.setup(helper);
        var local = warehouses(helper, world);
        local.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        Villager porter = spawnPorter(world.level(), world.route().villageId(), local.corePos());
        // A saved unpaid ticket predates the repair's bill.
        VillagerSimData.setRiverHaul(porter, new VillagerSimData.RiverHaul(world.route().id(),
                local.corePos(), local.homeDock(), "minecraft:cobblestone", 32, false, false, "pickup"));
        var project = world.data().createProject(world.route().villageId(), "repair", 20, local.corePos());
        project.setReservation("minecraft:cobblestone", 64);
        VillageRiverPorterService.handlePorter(porter, world.level(), null);
        if (count(local.core(), Items.COBBLESTONE) != 64
                || VillagerSimData.hasWorkCargo(porter, world.level().registryAccess(), 16)
                || VillagerSimData.riverHaul(porter).isPresent()) {
            helper.fail("River Porter ignored new actual repair reservations", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void realProjectBillChangesCategorySurplusPlan(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.source().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        f.source().setItem(1, new ItemStack(Items.STONE, 64));
        var data = VillageSavedData.get(f.level());
        var origin = data.village(f.origin()).orElseThrow();
        var destination = data.village(f.destination()).orElseThrow();
        var stock = VillageInterSettlementFreightService.categoryInventory(
                VillageStorageService.containers(f.origin(), f.level()));
        if (!VillageInterSettlementFreightService.categoryTradeEligible(origin, destination,
                stock, java.util.Map.of(), f.source().getItem(0),
                VillageResourceReservations.capture(data, origin))) {
            helper.fail("Actual unreserved category surplus should be exportable", MARK); return;
        }
        var project = data.createProject(f.origin(), "repair", 20, f.sourcePos());
        project.setReservation("minecraft:stone", 32);
        if (VillageInterSettlementFreightService.categoryTradeEligible(origin, destination,
                stock, java.util.Map.of(), f.source().getItem(0),
                VillageResourceReservations.capture(data, origin))) {
            helper.fail("Actual active project bill did not protect category reserve", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "project_reservations")
    public static void oversizedReservationMapNeverProvidesPartialSnapshot(GameTestHelper helper) {
        Fixture f = setup(helper);
        var data = VillageSavedData.get(f.level());
        var project = data.createProject(f.origin(), "repair", 20, f.sourcePos());
        for (int i = 0; i <= VillageResourceReservations.MAX_ENTRIES; i++)
            project.setReservation("unknown:item_" + i, 1);
        if (VillageResourceReservations.capture(data, data.village(f.origin()).orElseThrow()).complete()) {
            helper.fail("Oversized reservation map must fail closed before enumeration", MARK); return;
        }
        helper.succeed();
    }

    private static Warehouses warehouses(GameTestHelper helper,
                                          VillageRiverCargoGameTests.Fixture world) {
        BlockPos core = helper.absolutePos(new BlockPos(2, 2, 7));
        BlockPos remote = helper.absolutePos(new BlockPos(14, 2, 7));
        helper.setBlock(new BlockPos(2, 2, 7), Blocks.BARREL);
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
        world.data().touch();
        if (!(world.level().getBlockEntity(core) instanceof Container coreContainer)
                || !(world.level().getBlockEntity(remote) instanceof Container remoteContainer))
            throw new IllegalStateException("Physical test warehouse Barrel is absent");
        return new Warehouses(coreContainer, remoteContainer, core, remote,
                helper.absolutePos(new BlockPos(1, 2, 5)),
                helper.absolutePos(new BlockPos(14, 2, 3)), outpost.id());
    }

    private static Villager spawnPorter(ServerLevel level, UUID villageId, BlockPos at) {
        Villager villager = EntityType.VILLAGER.create(level);
        if (villager == null) throw new IllegalStateException("Villager create failed");
        move(villager, at);
        if (!level.addFreshEntity(villager))
            throw new IllegalStateException("Real Porter spawn failed");
        VillagerSimData.setVillageId(villager, villageId);
        VillagerSimData.setDuty(villager, "porter", level.getGameTime());
        return villager;
    }

    private static void move(Villager villager, BlockPos at) {
        // This transaction-only test places an actual Villager adjacent to
        // each container; live pathfinding remains a separate acceptance gate.
        villager.setPos(at.getX() + 0.5D, at.getY() + 1.0D, at.getZ() + 0.5D);
    }

    private record Warehouses(Container core, Container remote, BlockPos corePos,
                              BlockPos remotePos, BlockPos homeDock, BlockPos remoteDock,
                              UUID outpostId) {}
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
