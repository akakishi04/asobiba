package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.*;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.common.damagesource.DamageContainer;
import net.neoforged.neoforge.event.entity.living.*;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class NativeEffectMasteryGameTests {
    @GameTest(template = "empty16x6x9", batch = "native_effect_mastery")
    public static void nativeFireAspectUsesShortFlashAndLongBurn(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var target = EntityType.PIG.create(helper.getLevel());
        var enchantment = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(Enchantments.FIRE_ASPECT);
        var effect = enchantment.value().getEffects(EnchantmentEffectComponents.POST_ATTACK).getFirst().effect();
        ItemStack flash = mastered(helper, Items.DIAMOND_SWORD, Enchantments.FIRE_ASPECT, 2, 1);
        effect.apply(helper.getLevel(), 2, new EnchantedItemInUse(flash, EquipmentSlot.MAINHAND, player), target, target.position());
        helper.assertTrue(target.getRemainingFireTicks() == 96, "Flash Burn must shorten actual native 160-tick ignition to96");
        target.clearFire();
        ItemStack longBurn = mastered(helper, Items.DIAMOND_SWORD, Enchantments.FIRE_ASPECT, 2, 0);
        effect.apply(helper.getLevel(), 2, new EnchantedItemInUse(longBurn, EquipmentSlot.MAINHAND, player), target, target.position());
        helper.assertTrue(target.getRemainingFireTicks() == 280, "Long Burn must extend actual native duration75%");
        effect.apply(helper.getLevel(), 2, new EnchantedItemInUse(flash, EquipmentSlot.MAINHAND, player), target, target.position());
        helper.assertTrue(target.getRemainingFireTicks() == 280, "Short ignition must not erase an existing longer burn");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "native_effect_mastery")
    public static void bindingVenomScalesActualRandomSlow(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var target = EntityType.SPIDER.create(helper.getLevel());
        var holder = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(Enchantments.BANE_OF_ARTHROPODS);
        var effect = holder.value().getEffects(EnchantmentEffectComponents.POST_ATTACK).getFirst().effect();
        var ordinary = new ItemStack(Items.DIAMOND_SWORD); ordinary.enchant(holder, 5);
        var enhanced = mastered(helper, Items.DIAMOND_SWORD, Enchantments.BANE_OF_ARTHROPODS, 5, 0);
        for (int seed = 0; seed < 12; seed++) {
            target.removeAllEffects(); target.getRandom().setSeed(seed);
            effect.apply(helper.getLevel(), 5, new EnchantedItemInUse(ordinary, EquipmentSlot.MAINHAND, player), target, target.position());
            int vanilla = target.getEffect(MobEffects.MOVEMENT_SLOWDOWN).getDuration();
            target.removeAllEffects(); target.getRandom().setSeed(seed);
            effect.apply(helper.getLevel(), 5, new EnchantedItemInUse(enhanced, EquipmentSlot.MAINHAND, player), target, target.position());
            helper.assertTrue(target.getEffect(MobEffects.MOVEMENT_SLOWDOWN).getDuration() == vanilla * 2,
                    "Binding Venom must double the same randomized native duration, without another roll");
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "native_effect_mastery")
    public static void breachChangesOnlyRemainingArmorReduction(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        player.setItemSlot(EquipmentSlot.MAINHAND, mastered(helper, Items.MACE, Enchantments.BREACH, 4, 0));
        var target = EntityType.ZOMBIE.create(helper.getLevel());
        // Equipment attribute modifiers are installed by the next living tick,
        // not synchronously by setItemSlot. Give this immediate fixture real armor.
        target.getAttribute(net.minecraft.world.entity.ai.attributes.Attributes.ARMOR).setBaseValue(14.0D);
        helper.assertTrue(target.getArmorValue() >= 10, "Heavy-armor fixture must satisfy the native armor threshold");
        var container = new DamageContainer(helper.getLevel().damageSources().playerAttack(player), 10.0F);
        new EnchantmentTweaksEvents().onBreachDamage(new LivingIncomingDamageEvent(target, container));
        helper.assertTrue(container.getNewDamage() == 10.0F, "Breach must not multiply incoming damage");
        container.setReduction(DamageContainer.Reduction.ARMOR, 4.0F);
        helper.assertTrue(Math.abs(container.getNewDamage() - 6.6F) < 0.0001F,
                "Heavy Armor Crusher must remove15% of real remaining armor reduction; remaining=" + container.getNewDamage());
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "native_effect_mastery")
    public static void forcedAttachmentReclaimsOneItemIntoEmptySlot(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var helmet = mastered(helper, Items.DIAMOND_HELMET, Enchantments.BINDING_CURSE, 1, 2);
        player.getInventory().setItem(0, helmet);
        var events = new CurseMasteryEvents();
        events.onEquipChanged(new LivingEquipmentChangeEvent(player, EquipmentSlot.HEAD, helmet.copy(), ItemStack.EMPTY));
        helper.assertTrue(!player.getItemBySlot(EquipmentSlot.HEAD).isEmpty() && player.getInventory().getItem(0).isEmpty(),
                "Forced Attachment must move the one real item back into an empty armor slot");
        var snapshot = player.getItemBySlot(EquipmentSlot.HEAD).copy();
        player.setItemSlot(EquipmentSlot.HEAD, ItemStack.EMPTY);
        events.onEquipChanged(new LivingEquipmentChangeEvent(player, EquipmentSlot.HEAD, snapshot, ItemStack.EMPTY));
        helper.assertTrue(player.getItemBySlot(EquipmentSlot.HEAD).isEmpty(), "Missing external item must never be recreated");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "native_effect_mastery")
    public static void strongerNativeLauncherPunchSuppressesAmmoSupplement(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var holder = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(Enchantments.PUNCH);
        var bow = new ItemStack(Items.BOW); bow.enchant(holder, 4);
        var ammo = new ItemStack(Items.ARROW); ammo.enchant(holder, 5);
        var arrow = new Arrow(helper.getLevel(), player, ammo, bow);
        arrow.setDeltaMovement(1, 0, 0);
        var target = EntityType.PIG.create(helper.getLevel());
        target.setDeltaMovement(Vec3.ZERO);
        var container = new DamageContainer(helper.getLevel().damageSources().arrow(arrow, player), 3.0F);
        new EnchantedArrowImpactEvents().onArrowPunch(new LivingDamageEvent.Post(target, container));
        helper.assertTrue(target.getDeltaMovement().equals(Vec3.ZERO),
                "Native launcher Punch IV=4 must beat diminishing ammo Punch V=3.5 without additive impulse");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "native_effect_mastery")
    public static void punchBranchesTransformNativeProjectileImpulse(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var target = EntityType.PIG.create(helper.getLevel());
        for (int branch = 0; branch < 3; branch++) {
            var bow = mastered(helper, Items.BOW, Enchantments.PUNCH, 2, branch);
            var arrow = new Arrow(helper.getLevel(), player, new ItemStack(Items.ARROW), bow) {
                void applyPunch(net.minecraft.world.entity.LivingEntity victim) {
                    super.doKnockback(victim, helper.getLevel().damageSources().arrow(this, player));
                }
            };
            arrow.setDeltaMovement(1, 0, 0);
            target.setDeltaMovement(Vec3.ZERO);
            arrow.applyPunch(target);
            Vec3 actual = target.getDeltaMovement();
            double x = branch == 0 ? 1.68D : branch == 1 ? 0.48D : 0.30D;
            double y = branch == 0 ? 0.10D : branch == 1 ? 0.82D : 0.025D;
            helper.assertTrue(Math.abs(actual.x - x) < 0.0001D && Math.abs(actual.y - y) < 0.0001D,
                    "Punch branch must transform actual native impulse; branch=" + branch + " motion=" + actual);
        }
        helper.assertTrue(target.getEffect(MobEffects.MOVEMENT_SLOWDOWN).getDuration() == 50,
                "Pinning must apply bounded2.5-second control with reduced actual Punch displacement");
        helper.succeed();
    }

    private static ItemStack mastered(GameTestHelper helper, net.minecraft.world.item.Item item,
                                      ResourceKey<Enchantment> key, int level, int branch) {
        var holder = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(key);
        var stack = new ItemStack(item); stack.enchant(holder, level);
        EnchantmentMasteryData.addMastery(stack, holder, 100);
        for (int i = 0; i <= branch; i++) EnchantmentMasteryData.cycleBranch(stack, holder);
        return stack;
    }
}
