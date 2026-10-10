package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.Container;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.vehicle.ChestBoat;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageRiverCarrierLifecycleGameTests {
    private static final BlockPos MARK = new BlockPos(8, 2, 4);

    private VillageRiverCarrierLifecycleGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "river_carrier_lifecycle")
    public static void destroyedCarrierReleasesRouteWithoutInventingReplacementCargo(GameTestHelper helper) {
        var f = VillageRiverCargoGameTests.setup(helper);
        f.source().setItem(0, new ItemStack(Items.OAK_CHEST_BOAT));
        f.source().setItem(1, new ItemStack(Items.COBBLESTONE, 64));
        ChestBoat boat = VillageRiverCargoService.tryLaunch(f.level(), f.data(), f.route());
        if (boat == null) {
            helper.fail("Cannot launch a real paid carrier", MARK);
            return;
        }
        var wreckArea = boat.getBoundingBox().inflate(3.0D);
        boat.hurt(f.level().damageSources().generic(), 100.0F);
        int dropped = f.level().getEntitiesOfClass(ItemEntity.class, wreckArea).stream()
                .filter(e -> e.getItem().is(Items.COBBLESTONE))
                .mapToInt(e -> e.getItem().getCount()).sum();
        if (!boat.isRemoved() || f.route().carrierEntityId() != null
                || count(f.source(), Items.COBBLESTONE) != 48 || dropped != 16
                || count(f.destination(), Items.COBBLESTONE) != 0
                || f.route().trafficScore() != 0
                || VillageRiverCargoService.tryLaunch(f.level(), f.data(), f.route()) != null) {
            helper.fail("Destroyed carrier must leave only vanilla real drops and no free new boat", MARK);
            return;
        }
        // Releasing the route only allows a new dispatch after another actual
        // boat item is provided; wreck cargo is never copied into the manifest.
        f.source().setItem(0, new ItemStack(Items.OAK_CHEST_BOAT));
        ChestBoat replacement = VillageRiverCargoService.tryLaunch(f.level(), f.data(), f.route());
        if (replacement == null || replacement.getUUID().equals(boat.getUUID())
                || !replacement.getUUID().equals(f.route().carrierEntityId())
                || count(f.source(), Items.OAK_CHEST_BOAT) != 0
                || count(f.source(), Items.COBBLESTONE) + count(replacement, Items.COBBLESTONE)
                    + dropped != 64) {
            helper.fail("Replacement dispatch failed exact real boat/material payment", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "river_carrier_lifecycle")
    public static void chunkUnloadedCarrierKeepsExclusiveRouteReservation(GameTestHelper helper) {
        var f = VillageRiverCargoGameTests.setup(helper);
        f.source().setItem(0, new ItemStack(Items.OAK_CHEST_BOAT));
        f.source().setItem(1, new ItemStack(Items.COBBLESTONE, 40));
        ChestBoat boat = VillageRiverCargoService.tryLaunch(f.level(), f.data(), f.route());
        if (boat == null) {
            helper.fail("Cannot launch carrier for unload event", MARK);
            return;
        }
        var id = boat.getUUID();
        boat.remove(Entity.RemovalReason.UNLOADED_TO_CHUNK);
        if (!id.equals(f.route().carrierEntityId())
                || count(boat, Items.COBBLESTONE) != 16
                || count(f.source(), Items.COBBLESTONE) != 24) {
            helper.fail("Unload was confused with destruction and released real cargo ownership", MARK);
            return;
        }
        helper.succeed();
    }

    private static int count(Container container, Item item) {
        int total = 0;
        for (int i = 0; i < container.getContainerSize(); i++)
            if (container.getItem(i).is(item)) total += container.getItem(i).getCount();
        return total;
    }
}
