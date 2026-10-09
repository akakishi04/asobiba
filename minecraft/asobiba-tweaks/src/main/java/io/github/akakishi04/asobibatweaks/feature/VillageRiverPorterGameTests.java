package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageRiverPorterGameTests {
    private VillageRiverPorterGameTests() {}

    @GameTest(template = "empty16x6x9")
    public static void corePorterStagesPhysicalShipment(GameTestHelper helper) {
        var world = VillageRiverCargoGameTests.setup(helper);
        var local = warehouses(helper, world);
        local.core().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        Villager porter = spawnPorter(world.level(), world.route().villageId(), local.corePos());
        if (!VillageRiverPorterService.handlePorter(porter, world.level(), null)
                || count(local.core(), Items.COBBLESTONE) != 32
                || VillagerSimData.workCargoCount(porter,
                    world.level().registryAccess(), 16, Items.COBBLESTONE) != 32
                || !VillagerSimData.riverHaul(porter).map(
                        h -> "delivery".equals(h.phase())).orElse(false)) {
            helper.fail("Physical core pickup must withdraw exactly 32 real items",
                    new BlockPos(2, 2, 7));
            return;
        }
        move(porter, local.homeDock());
        VillageRiverPorterService.handlePorter(porter, world.level(), null);
        if (count(local.core(), Items.COBBLESTONE) != 32
                || count(world.source(), Items.COBBLESTONE) != 32
                || count(local.remote(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(porter, world.level().registryAccess(), 16)
                || VillagerSimData.riverHaul(porter).isPresent()) {
            helper.fail("Core-to-dock transport duplicated, lost or teleported stock",
                    new BlockPos(2, 2, 7));
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9")
    public static void remotePorterCollectsOnlyArrivedFreight(GameTestHelper helper) {
        var world = VillageRiverCargoGameTests.setup(helper);
        var local = warehouses(helper, world);
        world.destination().setItem(0, new ItemStack(Items.COBBLESTONE, 16));
        world.route().recordDockDelivery(true, "minecraft:cobblestone", 16);
        world.data().touch();
        Villager porter = spawnPorter(world.level(), world.route().villageId(), local.remoteDock());
        if (!VillageRiverPorterService.handlePorter(
                    porter, world.level(), local.outpostId())
                || count(world.destination(), Items.COBBLESTONE) != 0
                || VillagerSimData.workCargoCount(porter,
                    world.level().registryAccess(), 16, Items.COBBLESTONE) != 16
                || !world.route().dockReceipts(true).isEmpty()) {
            helper.fail("Porter did not collect exactly the receipted physical dock arrival",
                    new BlockPos(14, 2, 7));
            return;
        }
        move(porter, local.remotePos());
        VillageRiverPorterService.handlePorter(porter, world.level(), local.outpostId());
        if (count(local.remote(), Items.COBBLESTONE) != 16
                || count(local.core(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(porter, world.level().registryAccess(), 16)
                || VillagerSimData.riverHaul(porter).isPresent()) {
            helper.fail("Outpost Porter did not deliver the same physical shipment",
                    new BlockPos(14, 2, 7));
            return;
        }
        // Receipt and cargo state must be serializable, not a runtime-only flag.
        CompoundTag tag = world.data().save(new CompoundTag(), world.level().registryAccess());
        VillageSavedData restored = VillageSavedData.load(tag, world.level().registryAccess());
        if (!restored.route(world.route().id()).orElseThrow()
                .dockReceipts(true).isEmpty()) {
            helper.fail("Consumed river delivery receipt reappeared after NBT reload",
                    new BlockPos(14, 2, 7));
            return;
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

    private static int count(Container container, net.minecraft.world.item.Item item) {
        int count = 0;
        for (int i = 0; i < container.getContainerSize(); i++) {
            ItemStack stack = container.getItem(i);
            if (stack.is(item)) count += stack.getCount();
        }
        return count;
    }

    private record Warehouses(Container core, Container remote, BlockPos corePos,
                              BlockPos remotePos, BlockPos homeDock, BlockPos remoteDock,
                              UUID outpostId) {}
}
