package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.entity.projectile.ThrownTrident;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class LoyaltyTridentMasteryGameTests {
    private static final BlockPos MARK = new BlockPos(4, 1, 4);
    private LoyaltyTridentMasteryGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "trident_mastery")
    public static void nativeReturnBranchesHaveBoundedDistinctMotion(GameTestHelper helper) {
        Vec3 forward = new Vec3(1, 0, 0);
        Vec3 sideways = new Vec3(0, 0, 1);
        Vec3 fast = forward;
        Vec3 pursuing = forward;
        for (int i = 0; i < 500; i++) {
            fast = LoyaltyTridentMasteryEvents.returnMotion(fast.scale(0.95D).add(forward.scale(0.05D)),
                    forward, forward, Vec3.ZERO, 1, 0, 1.0D);
            pursuing = LoyaltyTridentMasteryEvents.returnMotion(pursuing.scale(0.95D).add(forward.scale(0.05D)),
                    forward, forward, forward, 1, 2, 1.0D);
        }
        Vec3 stationaryOwner = LoyaltyTridentMasteryEvents.returnMotion(forward,
                forward, forward, Vec3.ZERO, 1, 2, 1.0D);
        Vec3 safe = LoyaltyTridentMasteryEvents.returnMotion(forward,
                forward, sideways, Vec3.ZERO, 1, 1, 1.0D);
        if (Math.abs(fast.length() - 1.5D) > 0.0001D
                || Math.abs(pursuing.length() - 1.3D) > 0.0001D
                || !stationaryOwner.equals(forward) || safe.z <= 0.0D || safe.length() > 1.0001D) {
            helper.fail("Native Loyalty sidegrades lost bounded speed or distinct steering", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "trident_mastery")
    public static void nativeReturnPreservesOwnershipItemAndSingleUseAcrossReload(GameTestHelper helper) {
        var owner = helper.makeMockServerPlayerInLevel();
        BlockPos world = helper.absolutePos(MARK);
        owner.setPos(world.getX() + 6.0D, world.getY(), world.getZ());
        var loyalty = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.LOYALTY);
        ItemStack original = new ItemStack(Items.TRIDENT);
        original.enchant(loyalty, 1);
        original.setDamageValue(17);
        EnchantmentMasteryData.addMastery(original, loyalty, 100);
        EnchantmentMasteryData.cycleBranch(original, loyalty);
        ThrownTrident trident = new ThrownTrident(helper.getLevel(), owner, original.copy());
        trident.setPos(world.getX(), world.getY(), world.getZ());
        trident.pickup = AbstractArrow.Pickup.ALLOWED;
        Vec3 outward = new Vec3(-0.2D, 0.0D, 0.0D);
        trident.setDeltaMovement(outward);
        var events = new LoyaltyTridentMasteryEvents();
        events.onReturningTridentTick(new EntityTickEvent.Post(trident));
        if (!trident.getDeltaMovement().equals(outward)
                || EnchantmentMasteryData.getMastery(trident.getPickupItemStackOrigin(), loyalty) != 100) {
            helper.fail("Mastery took over an outbound trident before vanilla return", MARK);
            return;
        }
        trident.setNoPhysics(true); // State entered by vanilla's own return logic.
        events.onReturningTridentTick(new EntityTickEvent.Post(trident));
        CompoundTag saved = trident.saveWithoutId(new CompoundTag());
        ThrownTrident restored = new ThrownTrident(helper.getLevel(), owner, ItemStack.EMPTY);
        restored.load(saved);
        restored.setOwner(owner);
        restored.setNoPhysics(true); // Vanilla re-enters return state after restoring its hit data.
        events.onReturningTridentTick(new EntityTickEvent.Post(restored));
        ItemStack returned = restored.getPickupItemStackOrigin();
        if (EnchantmentMasteryData.getMastery(returned, loyalty) != 101
                || returned.getCount() != 1 || returned.getDamageValue() != 17
                || EnchantmentMasteryData.getBranch(returned, loyalty) != 0
                || restored.getOwner() != owner || restored.pickup != AbstractArrow.Pickup.ALLOWED
                || !owner.getInventory().isEmpty() || trident.isRemoved() || restored.isRemoved()
                || EnchantmentMasteryData.getMastery(original, loyalty) != 100) {
            helper.fail("Native return altered item ownership/payment or duplicated mastery after reload", MARK);
            return;
        }
        helper.succeed();
    }
}
