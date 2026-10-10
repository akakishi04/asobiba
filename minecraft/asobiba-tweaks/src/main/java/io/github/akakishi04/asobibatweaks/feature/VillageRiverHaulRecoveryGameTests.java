package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageRiverHaulRecoveryGameTests {
    private static final BlockPos MARK = new BlockPos(2, 2, 7);
    private VillageRiverHaulRecoveryGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "river_haul_recovery")
    public static void canceledRiverRouteReturnsRealParcelAndOnlyActualDockReceipt(GameTestHelper helper) {
        Fixture f = pickup(helper);
        f.world().route().setState("suspended");
        VillageRiverPorterService.handlePorter(f.porter(), helper.getLevel(), null);
        VillageRiverPorterService.handlePorter(f.porter(), helper.getLevel(), null);
        if (count(f.world().source(), Items.COBBLESTONE) != 32
                || count(f.world().destination(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(f.porter(), helper.getLevel().registryAccess(), 16)
                || VillagerSimData.riverHaul(f.porter()).isPresent()
                || f.world().route().dockReceipts(false).getOrDefault("minecraft:cobblestone", 0) != 32
                || f.world().route().trafficScore() != 0) {
            helper.fail("Canceled local river freight duplicated cargo or lost its actual return receipt", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "river_haul_recovery")
    public static void riverRecoveryRetainsPaidCargoAcrossReloadAndVillageMigration(GameTestHelper helper) {
        Fixture f = pickup(helper);
        for (int i = 0; i < f.world().source().getContainerSize(); i++)
            f.world().source().setItem(i, new ItemStack(Items.DIRT, 64));
        // The other real store is also full, so recovery cannot silently relocate.
        for (int i = 0; i < f.world().destination().getContainerSize(); i++)
            f.world().destination().setItem(i, new ItemStack(Items.DIRT, 64));
        f.world().route().setState("suspended");
        VillageRiverPorterService.handlePorter(f.porter(), helper.getLevel(), null);
        CompoundTag saved = f.porter().saveWithoutId(new CompoundTag());
        Villager restored = EntityType.VILLAGER.create(helper.getLevel());
        if (restored == null) throw new IllegalStateException("Missing restored Porter");
        restored.load(saved); f.porter().discard();
        UUID foreign = f.world().data().createVillage(f.sourcePos().offset(0, 0, 1),
                helper.getLevel().getGameTime()).id();
        VillagerSimData.setVillageId(restored, foreign);
        f.world().source().setItem(0, ItemStack.EMPTY);
        VillageRiverPorterService.handlePorter(restored, helper.getLevel(), null);
        if (count(f.world().source(), Items.COBBLESTONE) != 32
                || count(f.world().destination(), Items.COBBLESTONE) != 0
                || VillagerSimData.hasWorkCargo(restored, helper.getLevel().registryAccess(), 16)
                || VillagerSimData.riverHaul(restored).isPresent()) {
            helper.fail("Recovery lost original village provenance or actual NBT parcel", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "river_haul_recovery")
    public static void canceledUnpaidRiverTicketNeverCreatesCargoOrReceipt(GameTestHelper helper) {
        var world = VillageRiverCargoGameTests.setup(helper);
        BlockPos from = helper.absolutePos(new BlockPos(1, 2, 5));
        BlockPos to = helper.absolutePos(new BlockPos(14, 2, 3));
        Villager porter = porter(helper, world.route().villageId(), from);
        world.source().setItem(0, new ItemStack(Items.COBBLESTONE, 32));
        VillagerSimData.setRiverHaul(porter, new VillagerSimData.RiverHaul(world.route().id(), from, to,
                "minecraft:cobblestone", 32, true, false, "pickup"));
        world.route().setState("suspended");
        VillageRiverPorterService.handlePorter(porter, helper.getLevel(), null);
        if (count(world.source(), Items.COBBLESTONE) != 32
                || VillagerSimData.hasWorkCargo(porter, helper.getLevel().registryAccess(), 16)
                || VillagerSimData.riverHaul(porter).isPresent()
                || !world.route().dockReceipts(false).isEmpty()) {
            helper.fail("Canceling unpaid river intent invented a refund or receipt", MARK);
            return;
        }
        helper.succeed();
    }

    private static Fixture pickup(GameTestHelper helper) {
        var world = VillageRiverCargoGameTests.setup(helper);
        BlockPos from = helper.absolutePos(new BlockPos(1, 2, 5));
        BlockPos to = helper.absolutePos(new BlockPos(14, 2, 3));
        Villager porter = porter(helper, world.route().villageId(), from);
        world.source().setItem(0, new ItemStack(Items.COBBLESTONE, 32));
        world.route().recordDockDelivery(false, "minecraft:cobblestone", 32);
        VillagerSimData.setRiverHaul(porter, new VillagerSimData.RiverHaul(world.route().id(), from, to,
                "minecraft:cobblestone", 32, true, false, "pickup"));
        VillageRiverPorterService.handlePorter(porter, helper.getLevel(), null);
        if (count(world.source(), Items.COBBLESTONE) != 0
                || VillagerSimData.workCargoCount(porter, helper.getLevel().registryAccess(),
                    16, Items.COBBLESTONE) != 32 || !world.route().dockReceipts(false).isEmpty())
            throw new IllegalStateException("Real receipted parcel was not physically picked up");
        return new Fixture(world, porter, from);
    }

    private static Villager porter(GameTestHelper helper, UUID village, BlockPos at) {
        Villager porter = EntityType.VILLAGER.create(helper.getLevel());
        if (porter == null) throw new IllegalStateException("Cannot create Porter");
        porter.setPos(at.getX() + .5, at.getY() + 1.0, at.getZ() + .5);
        porter.setNoAi(true);
        if (!helper.getLevel().addFreshEntity(porter)) throw new IllegalStateException("Cannot spawn Porter");
        VillagerSimData.setVillageId(porter, village);
        VillagerSimData.setDuty(porter, "porter", helper.getLevel().getGameTime());
        return porter;
    }
    private static int count(Container c, Item item) {
        int total = 0;
        for (int i = 0; i < c.getContainerSize(); i++) if (c.getItem(i).is(item)) total += c.getItem(i).getCount();
        return total;
    }
    private record Fixture(VillageRiverCargoGameTests.Fixture world, Villager porter, BlockPos sourcePos) {}
}
