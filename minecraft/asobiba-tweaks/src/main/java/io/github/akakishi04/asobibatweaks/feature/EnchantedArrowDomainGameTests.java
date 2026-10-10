package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.entity.projectile.ThrownTrident;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.common.damagesource.DamageContainer;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class EnchantedArrowDomainGameTests {
    private static final BlockPos MARK = new BlockPos(4, 1, 4);
    private EnchantedArrowDomainGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "ammo_domain")
    public static void nativeTridentNeverReceivesArrowOnlyDamageOrFlightEffects(GameTestHelper helper) {
        var owner = helper.makeMockServerPlayerInLevel();
        var registry = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT);
        ItemStack item = new ItemStack(Items.TRIDENT);
        item.enchant(registry.getOrThrow(Enchantments.IMPALING), 3);
        // Forced command-only enchantments must not turn another AbstractArrow
        // subtype into supported Arrow ammunition either.
        item.enchant(registry.getOrThrow(Enchantments.POWER), 3);
        item.enchant(registry.getOrThrow(Enchantments.PIERCING), 3);
        item.enchant(registry.getOrThrow(Enchantments.FLAME), 1);
        ThrownTrident trident = new ThrownTrident(helper.getLevel(), owner, item);
        var events = new EnchantedArrowImpactEvents();
        events.onArrowJoined(new EntityJoinLevelEvent(trident, helper.getLevel()));
        Vec3 velocity = new Vec3(0.6D, 0.2D, 0.0D);
        trident.setDeltaMovement(velocity);
        events.onArrowTick(new EntityTickEvent.Post(trident));
        var squid = EntityType.SQUID.create(helper.getLevel());
        if (squid == null) throw new IllegalStateException("Cannot create aquatic target");
        var damage = new LivingIncomingDamageEvent(squid, new DamageContainer(
                helper.getLevel().damageSources().trident(trident, owner), 8.0F));
        events.onEnchantedArrowHit(damage);
        if (damage.getAmount() != 8.0F || squid.isOnFire() || trident.isOnFire()
                || trident.getPierceLevel() != 0 || !trident.getDeltaMovement().equals(velocity)) {
            helper.fail("Arrow ammo hooks double-applied native Trident effects", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "ammo_domain")
    public static void stationaryLoyaltyTridentIsNeverClaimedByArrowReturn(GameTestHelper helper) {
        var owner = helper.makeMockServerPlayerInLevel();
        ItemStack item = new ItemStack(Items.TRIDENT);
        item.enchant(helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.LOYALTY), 3);
        ThrownTrident trident = new ThrownTrident(helper.getLevel(), owner, item);
        trident.setDeltaMovement(Vec3.ZERO);
        trident.tickCount = 6;
        trident.pickup = AbstractArrow.Pickup.ALLOWED;
        var events = new LoyaltyArrowEvents();
        events.onArrowPostTick(new EntityTickEvent.Post(trident));
        // Also guard an old save polluted by the former broad AbstractArrow hook.
        trident.getPersistentData().putBoolean("asobibatweaks_loyalty_return_active", true);
        events.onArrowPreTick(new EntityTickEvent.Pre(trident));
        if (LoyaltyArrowEvents.isLoyaltyArrow(trident)
                || trident.pickup != AbstractArrow.Pickup.ALLOWED || trident.isRemoved()
                || trident.isNoPhysics() || !trident.getDeltaMovement().equals(Vec3.ZERO)
                || trident.getPersistentData().getBoolean("asobibatweaks_loyalty_return_queued")) {
            helper.fail("Arrow return controller took over the native trident", MARK);
            return;
        }
        helper.succeed();
    }
}
