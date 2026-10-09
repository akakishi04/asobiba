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

    @GameTest(template = "empty16x6x9")
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

    @GameTest(template = "empty16x6x9")
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

    @GameTest(template = "empty16x6x9")
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

    @GameTest(template = "empty16x6x9")
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

    @GameTest(template = "empty16x6x9")
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
