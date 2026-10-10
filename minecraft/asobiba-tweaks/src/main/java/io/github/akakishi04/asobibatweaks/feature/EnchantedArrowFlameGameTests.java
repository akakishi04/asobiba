package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CampfireBlock;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Real projectile fire state, vanilla block response and persistence regressions. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class EnchantedArrowFlameGameTests {
    private static final BlockPos MARK = new BlockPos(4, 1, 4);
    private EnchantedArrowFlameGameTests() {}

    @GameTest(template = "empty16x6x9", timeoutTicks = 30, batch = "ammo_flame")
    public static void flameAmmoLightsVanillaCampfireWithoutFlameLauncher(GameTestHelper helper) {
        BlockPos flameTarget = MARK;
        BlockPos normalTarget = MARK.offset(5, 0, 0);
        helper.setBlock(flameTarget.below(), Blocks.STONE);
        helper.setBlock(normalTarget.below(), Blocks.STONE);
        helper.setBlock(flameTarget, Blocks.CAMPFIRE.defaultBlockState().setValue(CampfireBlock.LIT, false));
        helper.setBlock(normalTarget, Blocks.CAMPFIRE.defaultBlockState().setValue(CampfireBlock.LIT, false));
        ItemStack enchanted = flameAmmo(helper);
        AbstractArrow flame = arrow(helper, enchanted, flameTarget);
        AbstractArrow ordinary = arrow(helper, new ItemStack(Items.ARROW), normalTarget);
        if (!helper.getLevel().addFreshEntity(flame) || !helper.getLevel().addFreshEntity(ordinary)) {
            helper.fail("Cannot spawn real test projectiles", MARK);
            return;
        }
        if (!flame.isOnFire() || ordinary.isOnFire()
                || !ItemStack.isSameItemSameComponents(enchanted, flame.getPickupItemStackOrigin())
                || flame.getPickupItemStackOrigin().getCount() != 1) {
            helper.fail("Only Flame ammo must ignite, without changing paid item identity", MARK);
            return;
        }
        helper.runAtTickTime(6, () -> {
            if (!helper.getLevel().getBlockState(helper.absolutePos(flameTarget)).getValue(CampfireBlock.LIT)
                    || helper.getLevel().getBlockState(helper.absolutePos(normalTarget)).getValue(CampfireBlock.LIT)) {
                helper.fail("Actual Flame arrow flight must light only its vanilla campfire", MARK);
                return;
            }
            flame.discard();
            ordinary.discard();
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "ammo_flame")
    public static void extinguishedFlameArrowStaysExtinguishedAfterNbtReload(GameTestHelper helper) {
        AbstractArrow original = arrow(helper, flameAmmo(helper), MARK);
        if (!helper.getLevel().addFreshEntity(original) || !original.isOnFire()) {
            helper.fail("Fresh Flame ammo did not ignite", MARK);
            return;
        }
        original.clearFire();
        CompoundTag saved = original.saveWithoutId(new CompoundTag());
        original.discard();
        AbstractArrow restored = EntityType.ARROW.create(helper.getLevel());
        if (restored == null) throw new IllegalStateException("Cannot restore arrow");
        restored.load(saved);
        if (!helper.getLevel().addFreshEntity(restored) || restored.isOnFire()
                || !ItemStack.isSameItemSameComponents(
                        restored.getPickupItemStackOrigin(), original.getPickupItemStackOrigin())) {
            helper.fail("Joining after NBT reload rekindled or changed extinguished ammunition", MARK);
            return;
        }
        restored.discard();
        // Older saves have no initialization marker; disk loads retain Fire.
        AbstractArrow legacy = arrow(helper, flameAmmo(helper), MARK);
        new EnchantedArrowImpactEvents().onArrowJoined(
                new EntityJoinLevelEvent(legacy, helper.getLevel(), true));
        if (legacy.isOnFire()) {
            helper.fail("Loading an older extinguished projectile restarted Flame", MARK);
            return;
        }
        helper.succeed();
    }

    private static ItemStack flameAmmo(GameTestHelper helper) {
        ItemStack ammo = new ItemStack(Items.ARROW);
        ammo.enchant(helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FLAME), 1);
        return ammo;
    }

    private static AbstractArrow arrow(GameTestHelper helper, ItemStack ammo, BlockPos target) {
        Villager owner = EntityType.VILLAGER.create(helper.getLevel());
        if (owner == null) throw new IllegalStateException("Cannot create arrow owner");
        AbstractArrow projectile = ((ArrowItem)ammo.getItem()).createArrow(
                helper.getLevel(), ammo.copyWithCount(1), owner, new ItemStack(Items.BOW));
        BlockPos worldTarget = helper.absolutePos(target);
        // Hit the actual low campfire collision shape inside the fixture.
        projectile.setPos(worldTarget.getX() - 1.5D, worldTarget.getY() + 0.25D,
                worldTarget.getZ() + 0.5D);
        projectile.setNoGravity(true);
        projectile.setDeltaMovement(new Vec3(1.0D, 0.0D, 0.0D));
        projectile.pickup = AbstractArrow.Pickup.ALLOWED;
        return projectile;
    }
}
