package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.neoforged.neoforge.common.damagesource.DamageContainer;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class ArrowAmmoMasteryGameTests {
    @GameTest(template = "empty16x6x9", batch = "ammo_mastery")
    public static void paidAmmoHistorySurvivesNativeSaveAndPickupWithoutReplay(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var registry = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT);
        var sharpness = registry.getOrThrow(Enchantments.SHARPNESS);
        var loyalty = registry.getOrThrow(Enchantments.LOYALTY);
        var source = new ItemStack(Items.ARROW, 7); source.enchant(sharpness, 1); source.enchant(loyalty, 1);
        player.getInventory().setItem(0, source);
        var arrow = new Arrow(helper.getLevel(), player, source.copyWithCount(1), new ItemStack(Items.BOW));
        arrow.pickup = AbstractArrow.Pickup.ALLOWED;
        var pig = EntityType.PIG.create(helper.getLevel());
        var event = new LivingDamageEvent.Post(pig, new DamageContainer(helper.getLevel().damageSources().arrow(arrow, player), 3));
        var hooks = new EnchantedArrowImpactEvents();
        hooks.onAmmoMasteryHit(event); hooks.onAmmoMasteryHit(event);
        helper.assertTrue(EnchantmentMasteryData.getMastery(arrow.getPickupItemStackOrigin(), sharpness) == 1,
                "Repeated hit callbacks must credit each ammo enchantment once per physical flight");
        helper.assertTrue(EnchantmentMasteryData.getMastery(source, sharpness) == 0 && source.getCount() == 7,
                "Remaining inventory ammunition must retain its own unchanged history and count");
        helper.assertTrue(EnchantmentMasteryData.getMastery(arrow.getPickupItemStackOrigin(), loyalty) == 0,
                "Impact must not duplicate Loyalty's separate successful-return credit");
        CompoundTag saved = arrow.saveWithoutId(new CompoundTag()); arrow.discard();
        var restored = EntityType.ARROW.create(helper.getLevel()); restored.load(saved);
        restored.setOwner(player);
        ArrowAmmoMasteryGrowth.hit(restored, pig);
        helper.assertTrue(EnchantmentMasteryData.getMastery(restored.getPickupItemStackOrigin(), sharpness) == 1,
                "Native entity save/load must preserve both mastery and one-use guard");
        var expected = restored.getPickupItemStackOrigin().copy();
        restored.setNoPhysics(true);
        restored.playerTouch(player);
        helper.assertTrue(restored.isRemoved(), "Native pickup must consume the physical projectile");
        int recovered = 0;
        for (int i = 0; i < player.getInventory().getContainerSize(); i++) {
            var stack = player.getInventory().getItem(i);
            if (ItemStack.isSameItemSameComponents(stack, expected)) recovered += stack.getCount();
        }
        helper.assertTrue(recovered == 1 && source.getCount() == 7,
                "Native pickup must return exactly one grown arrow without changing other components or ammo");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "ammo_mastery")
    public static void ammoHistoryHonorsTargetConditionsRecoveryAndGrowthConfig(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var smite = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(Enchantments.SMITE);
        var ammo = new ItemStack(Items.ARROW); ammo.enchant(smite, 1);
        var arrow = new Arrow(helper.getLevel(), player, ammo, new ItemStack(Items.BOW));
        arrow.pickup = AbstractArrow.Pickup.ALLOWED;
        ArrowAmmoMasteryGrowth.hit(arrow, EntityType.PIG.create(helper.getLevel()));
        helper.assertTrue(EnchantmentMasteryData.getMastery(arrow.getPickupItemStackOrigin(), smite) == 0,
                "Smite must not grow from non-undead impacts");
        boolean enabled = AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean();
        try {
            AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.set(false);
            ArrowAmmoMasteryGrowth.hit(arrow, EntityType.ZOMBIE.create(helper.getLevel()));
            helper.assertTrue(EnchantmentMasteryData.getMastery(arrow.getPickupItemStackOrigin(), smite) == 0,
                    "Disabled growth must neither grant nor consume a credit");
        } finally { AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.set(enabled); }
        arrow.pickup = AbstractArrow.Pickup.DISALLOWED;
        ArrowAmmoMasteryGrowth.hit(arrow, EntityType.ZOMBIE.create(helper.getLevel()));
        helper.assertTrue(EnchantmentMasteryData.getMastery(arrow.getPickupItemStackOrigin(), smite) == 0,
                "Synthetic or Multishot secondary ammunition must not gain recoverable history");
        arrow.pickup = AbstractArrow.Pickup.ALLOWED;
        ArrowAmmoMasteryGrowth.hit(arrow, EntityType.ZOMBIE.create(helper.getLevel()));
        helper.assertTrue(EnchantmentMasteryData.getMastery(arrow.getPickupItemStackOrigin(), smite) == 1,
                "A qualifying paid-arrow hit must grant its own one-use history");
        helper.succeed();
    }
}
