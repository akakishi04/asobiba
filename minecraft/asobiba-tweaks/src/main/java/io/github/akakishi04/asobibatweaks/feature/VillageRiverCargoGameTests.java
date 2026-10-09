package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.vehicle.ChestBoat;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * Live GameTestServer freight scenarios.
 *
 * Builds an actual 16x6x9 loaded WATER corridor with TWO physical dock
 * Barrels and registered durable village infrastructure, then calls the
 * exact production launch and carrier tick methods. Vanilla boat physics,
 * real block entities, NeoForge events, SavedData and inventory mutation
 * all run on the logical server; no fake Container is involved.
 *
 * Only the OFF-by-default experimental event gate is bypassed. These tests
 * do not enable river cargo in an ordinary user's world or simulate a GUI.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageRiverCargoGameTests {
    private static final BlockPos BANK_LEFT = new BlockPos(0, 1, 4);
    private static final BlockPos BANK_RIGHT = new BlockPos(15, 1, 4);
    private static final BlockPos TEST_MARKER = new BlockPos(8, 2, 4);

    private VillageRiverCargoGameTests() {}

    @GameTest(template = "empty16x6x9", timeoutTicks = 340)
    public static void realChestBoatDeliversAndReturnsWithExactInventory(GameTestHelper helper) {
        Fixture test = setup(helper);
        // GameTestServer runs without a human player: add a real server-side
        // observer to activate entity-ticking chunks as in survival gameplay.
        ServerPlayer observer = helper.makeMockServerPlayerInLevel();
        observer.setPos(test.start().getX() - 2.5D,
                test.start().getY() + 1.0D, test.start().getZ() - 3.5D);

        test.source().setItem(0, new ItemStack(Items.OAK_CHEST_BOAT));
        test.source().setItem(1, new ItemStack(Items.COBBLESTONE, 40));
        ChestBoat boat = VillageRiverCargoService.tryLaunch(
                test.level(), test.data(), test.route());

        if (boat == null || !boat.isAlive()
                || !boat.getUUID().equals(test.route().carrierEntityId())
                || test.source().getItem(0).getCount() != 0
                || count(test.source(), Items.COBBLESTONE) != 24
                || count(boat, Items.COBBLESTONE) != 16
                || count(test.destination(), Items.COBBLESTONE) != 0) {
            helper.fail("Boat dispatch did not consume one real boat and load exactly 16 cargo", TEST_MARKER);
            return;
        }

        AtomicBoolean physicallyMoved = new AtomicBoolean(false);
        AtomicInteger previousVanillaTick = new AtomicInteger(boat.tickCount);
        for (int tick = 1; tick <= 330; tick++) {
            final int elapsed = tick;
            helper.runAtTickTime(tick, () -> {
                if (!boat.isAlive()) {
                    helper.fail("Carrier was destroyed during live navigation", TEST_MARKER);
                    return;
                }
                // GameTestServer often stops entity-ticking boat chunks after
                // their initial few ticks, even with a mock player. Advance
                // the ACTUAL vanilla ChestBoat.tick() only if the server did
                // not update it during this GameTest tick; do not teleport
                // or bypass collisions, buoyancy or vanilla inventory logic.
                boolean naturallyTicked = boat.tickCount > previousVanillaTick.get();
                if (!naturallyTicked) boat.tick();
                previousVanillaTick.set(boat.tickCount);
                // When the feature defaults ON, NeoForge already ran the
                // production boat event for naturally ticked entities. Do
                // not run the same state machine twice in one game tick.
                // Direct vanilla ticks need an explicit controller callback
                // because a standalone boat.tick() emits no Post event.
                if (!naturallyTicked
                        || !io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig
                                .VILLAGE_RIVER_CARGO_ENABLED.getAsBoolean()) {
                    VillageRiverCargoService.tickCarrier(boat, test.level());
                }
                if (horizontalDistance(boat, test.start()) > 3.0D) physicallyMoved.set(true);
                int source = count(test.source(), Items.COBBLESTONE);
                int aboard = count(boat, Items.COBBLESTONE);
                int received = count(test.destination(), Items.COBBLESTONE);
                if (source + aboard + received != 40) {
                    helper.fail("Freight duplicated or lost actual items at game tick " + elapsed, TEST_MARKER);
                    return;
                }
                if (source != 24 || received > 16
                        || !boat.getUUID().equals(test.route().carrierEntityId())) {
                    helper.fail("Boat ownership or source/destination stock changed illegally", TEST_MARKER);
                    return;
                }
                if (received == 16 && aboard == 0 && physicallyMoved.get()
                        && horizontalDistance(boat, test.start()) < 1.4D
                        && "idle".equals(boat.getPersistentData()
                                .getString("asobibatweaks_river_cargo_phase"))) {
                    helper.succeed();
                } else if (elapsed == 330) {
                    BlockPos target = test.route().waypoints().getLast();
                    double dx = target.getX() + 0.5D - boat.getX();
                    double dz = target.getZ() + 0.5D - boat.getZ();
                    double norm = Math.max(1.0E-6D, Math.hypot(dx, dz));
                    BlockPos ahead = new BlockPos(
                            (int)Math.floor(boat.getX() + dx / norm * 1.5D),
                            test.route().from().getY(),
                            (int)Math.floor(boat.getZ() + dz / norm * 1.5D));
                    helper.fail("Live boat did not finish outbound unloading and return within 330 ticks"
                            + "; received=" + received + ", aboard=" + aboard
                            + ", x=" + boat.getX() + ", z=" + boat.getZ()
                            + ", phase=" + boat.getPersistentData()
                                    .getString("asobibatweaks_river_cargo_phase")
                            + ", boatTickCount=" + boat.tickCount
                            + ", velocity=" + boat.getDeltaMovement()
                            + ", y=" + boat.getY()
                            + ", vehicle=" + boat.isVehicle()
                            + ", courseMatch=" + (test.route().waypoints().hashCode()
                                    == boat.getPersistentData().getInt(
                                            "asobibatweaks_river_course"))
                            + ", carrierMatch=" + boat.getUUID().equals(
                                    test.route().carrierEntityId())
                            + ", routeState=" + test.route().state()
                            + ", waypointIndex=" + boat.getPersistentData()
                                    .getInt("asobibatweaks_river_cargo_cursor")
                            + ", ahead=" + ahead
                            + ", aheadWater=" + test.level().getFluidState(ahead).isSource()
                            + ", aheadAir=" + test.level().getBlockState(ahead.above()).isAir()
                            + ", aheadNavigable=" + VillageRiverNavigationService.navigable(
                                    test.level(), ahead)
                            + ", actualDockContainer=" + (VillageRiverCargoService.dockBarrel(
                                    test.level(), test.data(), test.route().villageId(),
                                    test.route().to()) != null)
                            + ", toDistance=" + horizontalDistance(boat, test.end())
                            + ", cargoManifest=" + boat.getPersistentData()
                                    .getString("asobibatweaks_river_cargo_item")
                            + ", dockReceipt=" + test.route().dockReceipts(true)
                            + ", dockSites=" + test.data()
                                    .workSitesForVillage(test.route().villageId()).stream()
                                    .filter(s -> "river_dock".equals(s.type()))
                                    .map(s -> s.state() + ":" + s.purpose()).toList()
                            + ", physicalBarrel=" + test.level().getBlockState(
                                    test.end().offset(3, 1, -1)).is(Blocks.BARREL)
                            + ", registeredStorage=" + test.data().storageAt(
                                    test.route().villageId(),
                                    test.end().offset(3, 1, -1)).isPresent(),
                            TEST_MARKER);
                }
            });
        }
    }

    @GameTest(template = "empty16x6x9", timeoutTicks = 60)
    public static void fullBarrelAndPlayerCargoNeverDeleteFreight(GameTestHelper helper) {
        Fixture test = setup(helper);
        test.source().setItem(0, new ItemStack(Items.OAK_CHEST_BOAT));
        test.source().setItem(1, new ItemStack(Items.COBBLESTONE, 40));
        // An entirely full target may still receive an arriving physical boat;
        // it must keep the whole shipment onboard until the space is free.
        for (int slot = 0; slot < test.destination().getContainerSize(); slot++) {
            test.destination().setItem(slot, new ItemStack(Items.DIRT, 64));
        }
        ChestBoat boat = VillageRiverCargoService.tryLaunch(
                test.level(), test.data(), test.route());
        if (boat == null) {
            helper.fail("A stocked source with a real boat should launch freight", TEST_MARKER);
            return;
        }

        // Positioning at a destination is done ONLY in this focused unloading
        // test. The other required test must traverse every water block.
        boat.setPos(test.end().getX() + 0.5D,
                test.end().getY() + 1.0D, test.end().getZ() + 0.5D);
        boat.getPersistentData().putString("asobibatweaks_river_cargo_phase", "unload");
        VillageRiverCargoService.tickCarrier(boat, test.level());
        if (count(boat, Items.COBBLESTONE) != 16
                || count(test.destination(), Items.COBBLESTONE) != 0) {
            helper.fail("Full dock Barrel consumed or duplicated arriving cargo", TEST_MARKER);
            return;
        }

        test.destination().setItem(26, ItemStack.EMPTY);
        boat.setItem(1, new ItemStack(Items.DIAMOND, 1));
        VillageRiverCargoService.tickCarrier(boat, test.level());
        if (count(boat, Items.COBBLESTONE) != 16
                || !boat.getItem(1).is(Items.DIAMOND)
                || count(test.destination(), Items.COBBLESTONE) != 0) {
            helper.fail("Courier illegally unloaded player-added unrelated boat cargo", TEST_MARKER);
            return;
        }

        boat.setItem(1, ItemStack.EMPTY);
        VillageRiverCargoService.tickCarrier(boat, test.level());
        if (count(test.source(), Items.COBBLESTONE) != 24
                || count(test.destination(), Items.COBBLESTONE) != 16
                || count(boat, Items.COBBLESTONE) != 0) {
            helper.fail("Courier failed to resume exact unloading after capacity recovered", TEST_MARKER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9")
    public static void noBoatItemNeverSpawnsBoatOrTransfersCargo(GameTestHelper helper) {
        Fixture test = setup(helper);
        test.source().setItem(0, new ItemStack(Items.COBBLESTONE, 40));
        ChestBoat boat = VillageRiverCargoService.tryLaunch(
                test.level(), test.data(), test.route());
        if (boat != null || test.route().carrierEntityId() != null
                || count(test.source(), Items.COBBLESTONE) != 40
                || count(test.destination(), Items.COBBLESTONE) != 0) {
            helper.fail("Unfunded route invented a boat or transferred cargo", TEST_MARKER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9")
    public static void actualBoatAndCarrierSavedDataRoundTrip(GameTestHelper helper) {
        Fixture test = setup(helper);
        test.source().setItem(0, new ItemStack(Items.OAK_CHEST_BOAT));
        test.source().setItem(1, new ItemStack(Items.COBBLESTONE, 40));
        ChestBoat boat = VillageRiverCargoService.tryLaunch(
                test.level(), test.data(), test.route());
        if (boat == null) {
            helper.fail("Cannot inspect a carrier that was not launched", TEST_MARKER);
            return;
        }

        CompoundTag dataTag = test.data().save(new CompoundTag(), test.level().registryAccess());
        VillageSavedData decoded = VillageSavedData.load(
                dataTag, test.level().registryAccess());
        var restoredRoute = decoded.route(test.route().id()).orElse(null);
        CompoundTag boatTag = boat.saveWithoutId(new CompoundTag());
        ChestBoat reconstructed = EntityType.CHEST_BOAT.create(test.level());
        if (reconstructed == null) {
            helper.fail("Vanilla ChestBoat entity factory failed", TEST_MARKER);
            return;
        }
        reconstructed.load(boatTag); // detached test-only object; never add to world
        if (restoredRoute == null
                || !boat.getUUID().equals(restoredRoute.carrierEntityId())
                || count(reconstructed, Items.COBBLESTONE) != 16
                || !reconstructed.getPersistentData().getUUID(
                        "asobibatweaks_river_cargo_route").equals(test.route().id())
                || !"outbound".equals(reconstructed.getPersistentData().getString(
                        "asobibatweaks_river_cargo_phase"))) {
            helper.fail("World SavedData or vanilla ChestBoat NBT lost carrier identity/cargo", TEST_MARKER);
            return;
        }
        helper.succeed();
    }

    /** Both directions spend and deliver real inventory, with per-dock receipts. */
    @GameTest(template = "empty16x6x9")
    public static void returnTripCarriesRealReverseFreightAndReceipts(GameTestHelper helper) {
        Fixture test = setup(helper);
        test.source().setItem(0, new ItemStack(Items.OAK_CHEST_BOAT));
        test.source().setItem(1, new ItemStack(Items.COBBLESTONE, 40));
        test.destination().setItem(0, new ItemStack(Items.WHEAT, 40));
        ChestBoat boat = VillageRiverCargoService.tryLaunch(
                test.level(), test.data(), test.route());
        if (boat == null || count(boat, Items.COBBLESTONE) != 16) {
            helper.fail("The actual forward freight must load 16 Cobblestone",
                    new BlockPos(8, 2, 4));
            return;
        }

        // Test only the two *real* dock transactions; GT11 independently
        // drives the complete vanilla boat travel between these docks.
        boat.setPos(test.end().getX() + 0.5D,
                test.end().getY() + 1.0D, test.end().getZ() + 0.5D);
        boat.getPersistentData().putString("asobibatweaks_river_cargo_phase", "unload");
        VillageRiverCargoService.tickCarrier(boat, test.level());
        if (count(test.destination(), Items.COBBLESTONE) != 16
                || count(test.destination(), Items.WHEAT) != 24
                || count(boat, Items.WHEAT) != 16
                || count(boat, Items.COBBLESTONE) != 0
                || test.route().dockReceipts(true)
                    .getOrDefault("minecraft:cobblestone", 0) != 16) {
            helper.fail("Remote dock did not unload outbound and load actual return goods",
                    new BlockPos(8, 2, 4));
            return;
        }

        boat.setPos(test.start().getX() + 0.5D,
                test.start().getY() + 1.0D, test.start().getZ() + 0.5D);
        boat.getPersistentData().putString(
                "asobibatweaks_river_cargo_phase", "return_unload");
        VillageRiverCargoService.tickCarrier(boat, test.level());
        if (count(test.source(), Items.COBBLESTONE) != 24
                || count(test.source(), Items.WHEAT) != 16
                || count(test.destination(), Items.COBBLESTONE) != 16
                || count(test.destination(), Items.WHEAT) != 24
                || !boat.getItem(0).isEmpty()
                || test.route().dockReceipts(false)
                    .getOrDefault("minecraft:wheat", 0) != 16
                || !"idle".equals(boat.getPersistentData().getString(
                        "asobibatweaks_river_cargo_phase"))) {
            helper.fail("Reverse freight disappeared, duplicated or failed to receipt",
                    new BlockPos(8, 2, 4));
            return;
        }
        helper.succeed();
    }

    static Fixture setup(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();

        // Everything remains inside this test's dedicated 16x6x9 structure.
        // Enclose the 14-long, 5-wide, one-block source-water corridor so
        // real liquid ticks do not flow into another test's world.
        for (int x = 0; x < 16; x++) {
            for (int z = 0; z < 9; z++) {
                helper.setBlock(new BlockPos(x, 0, z), Blocks.STONE);
                // NBT structure dimensions do not guarantee an empty build
                // volume when the game-test world already has terrain. Clear
                // the complete boat headroom explicitly before each run:
                // otherwise valid source water can have stone above it, and
                // the safety guard correctly refuses to sail into the block.
                for (int y = 2; y <= 5; y++) {
                    helper.setBlock(new BlockPos(x, y, z), Blocks.AIR);
                }
                boolean channel = x >= 1 && x <= 14 && z >= 2 && z <= 6;
                if (!channel) helper.setBlock(new BlockPos(x, 1, z), Blocks.STONE);
            }
        }
        for (int x = 1; x <= 14; x++) {
            for (int z = 2; z <= 6; z++) {
                helper.setBlock(new BlockPos(x, 1, z), Blocks.WATER);
            }
        }

        // Genuine dock decks and Barrel block entities (no fake containers).
        for (BlockPos local : List.of(
                BANK_LEFT.above(), BANK_LEFT.relative(net.minecraft.core.Direction.EAST).above(),
                BANK_LEFT.relative(net.minecraft.core.Direction.EAST, 2).above(),
                BANK_RIGHT.above(), BANK_RIGHT.relative(net.minecraft.core.Direction.WEST).above(),
                BANK_RIGHT.relative(net.minecraft.core.Direction.WEST, 2).above())) {
            helper.setBlock(local, Blocks.OAK_PLANKS);
        }
        BlockPos leftStorage = BANK_LEFT.relative(net.minecraft.core.Direction.SOUTH).above();
        BlockPos rightStorage = BANK_RIGHT.relative(net.minecraft.core.Direction.NORTH).above();
        helper.setBlock(leftStorage, Blocks.BARREL);
        helper.setBlock(rightStorage, Blocks.BARREL);

        BlockPos leftBank = helper.absolutePos(BANK_LEFT);
        BlockPos rightBank = helper.absolutePos(BANK_RIGHT);
        BlockPos leftBarrel = helper.absolutePos(leftStorage);
        BlockPos rightBarrel = helper.absolutePos(rightStorage);
        BlockPos from = leftBank.relative(net.minecraft.core.Direction.EAST, 3);
        BlockPos to = rightBank.relative(net.minecraft.core.Direction.WEST, 3);

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village =
                data.createVillage(leftBank, level.getGameTime());
        registerDock(data, village.id(), leftBank, leftBarrel, "east");
        registerDock(data, village.id(), rightBank, rightBarrel, "west");

        List<BlockPos> routePoints = VillageRiverNavigationService.findLoadedPath(
                level, from, to);
        if (routePoints.size() != 2 || !routePoints.getFirst().equals(from)
                || !routePoints.getLast().equals(to)) {
            helper.fail("Two real dock berths are not connected by navigable water", TEST_MARKER);
        }
        VillageSavedData.RouteRecord route =
                data.createRoute(village.id(), "river", from, to);
        data.setRouteWaypoints(route.id(), routePoints);
        route.setState("active");
        data.touch();

        if (!(level.getBlockEntity(leftBarrel) instanceof Container src)
                || !(level.getBlockEntity(rightBarrel) instanceof Container dst)) {
            helper.fail("Real Barrel block entities missing from GameTest structure", TEST_MARKER);
            throw new IllegalStateException("GameTest Barrels not created");
        }
        return new Fixture(level, data, route, src, dst, from, to);
    }

    private static void registerDock(VillageSavedData data, UUID villageId, BlockPos bank,
                                     BlockPos barrel, String direction) {
        VillageSavedData.ProjectRecord project =
                data.createProject(villageId, "building", 55, bank);
        project.setTemplateId(VillageRiverDockService.TEMPLATE);
        project.setPhase("complete");
        project.setWorkCursor(4);
        project.setParameter("dock_direction", direction);
        project.setParameter("dock_water_y", Integer.toString(bank.getY()));
        project.setParameter("dock_plank", "minecraft:oak_planks");

        VillageSavedData.WorkSiteRecord dock = data.createWorkSite(
                villageId, "river_dock",
                bank.offset(-3, -1, -2), bank.offset(3, 3, 2));
        dock.setState("active");
        dock.setPurpose("dock:" + project.id());
        VillageSavedData.StorageRecord stored =
                data.createStorage(villageId, barrel, "general");
        stored.setValidationState("valid");
    }

    private static int count(Container container, net.minecraft.world.item.Item item) {
        int total = 0;
        for (int index = 0; index < container.getContainerSize(); index++) {
            ItemStack stack = container.getItem(index);
            if (stack.is(item)) total += stack.getCount();
        }
        return total;
    }

    private static double horizontalDistance(ChestBoat boat, BlockPos from) {
        double dx = boat.getX() - from.getX() - 0.5D;
        double dz = boat.getZ() - from.getZ() - 0.5D;
        return Math.sqrt(dx * dx + dz * dz);
    }

    static record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.RouteRecord route,
                           Container source, Container destination,
                           BlockPos start, BlockPos end) {}
}
