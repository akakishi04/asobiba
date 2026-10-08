package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.component.DataComponents;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/**
 * Quick Charge mastery is stored on the weapon, with timestamped firing
 * history. All three branches use the ordinary Quick Charge charge duration
 * as a baseline and never create free ammunition.
 */
public final class LauncherReloadMasteryEvents {
    private static final String LAST_SHOT = "asobibatweaks_quick_charge_last_shot";
    private static final String STREAK = "asobibatweaks_quick_charge_reload_streak";

    public static Branch branch(ItemStack weapon, String id) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || weapon.isEmpty()) return null;
        for (var holder : EnchantmentMasteryData.enchantments(weapon).keySet()) {
            if (!id.equals(EnchantmentMasteryData.id(holder))) continue;
            int mastery = EnchantmentMasteryData.getMastery(weapon, holder);
            int branch = EnchantmentMasteryData.getBranch(weapon, holder);
            return mastery >= 50 && branch >= 0 && branch < 3
                    ? new Branch(mastery, branch) : null;
        }
        return null;
    }

    public static int chargeDuration(ItemStack weapon, LivingEntity shooter, int vanilla) {
        if (!weapon.is(Items.CROSSBOW) || vanilla <= 1) return vanilla;
        Branch branch = branch(weapon, "minecraft:quick_charge");
        if (branch == null || branch.choice() == 2) return vanilla;

        double strength = branch.progress();
        CustomData data = weapon.get(DataComponents.CUSTOM_DATA);
        long last = data == null ? Long.MIN_VALUE : data.copyTag().getLong(LAST_SHOT);
        int streak = data == null ? 0 : data.copyTag().getInt(STREAK);
        long now = shooter.level().getGameTime();
        long elapsed = now >= last ? now - last : Long.MAX_VALUE;
        double fraction = 1.0D;

        if (branch.choice() == 0 && elapsed >= 60L) {
            fraction -= 0.10D + 0.20D * strength;
        } else if (branch.choice() == 1 && elapsed <= 60L) {
            // Each successful prior release contributes; first reload
            // after inactivity retains vanilla speed.
            double perShot = 0.05D + 0.05D * strength;
            double cap = 0.15D + 0.15D * strength;
            fraction -= Math.min(cap, streak * perShot);
        }
        return Math.max(1, (int)Math.ceil(vanilla * fraction));
    }

    public static void onFired(ServerLevel level, LivingEntity shooter, ItemStack weapon) {
        if (!(shooter instanceof ServerPlayer)
                || !weapon.is(Items.CROSSBOW)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;
        Branch branch = branch(weapon, "minecraft:quick_charge");
        if (branch == null) return;

        CustomData original = weapon.get(DataComponents.CUSTOM_DATA);
        long before = original == null ? Long.MIN_VALUE
                : original.copyTag().getLong(LAST_SHOT);
        int count = original == null ? 0 : original.copyTag().getInt(STREAK);
        long now = level.getGameTime();
        int next = now >= before && now - before <= 60L
                ? Math.min(3, count + 1) : 1;
        CustomData.update(DataComponents.CUSTOM_DATA, weapon, tag -> {
            tag.putLong(LAST_SHOT, now);
            tag.putInt(STREAK, next);
        });
    }

    @SubscribeEvent
    public void onMobileReload(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !player.isUsingItem()) return;
        ItemStack item = player.getUseItem();
        if (!item.is(Items.CROSSBOW)
                || branch(item, "minecraft:quick_charge") == null
                || branch(item, "minecraft:quick_charge").choice() != 2) return;

        Branch branch = branch(item, "minecraft:quick_charge");
        double horizontal = player.getDeltaMovement().horizontalDistance();
        if (horizontal < 0.015D || horizontal > 0.35D || !player.onGround()) return;
        double compensation = 0.15D + 0.35D * branch.progress();
        // This is a bounded movement correction while actually charging,
        // rather than a permanent movement-speed attribute modifier.
        double multiplier = 1.0D + 0.20D * compensation;
        player.setDeltaMovement(
                player.getDeltaMovement().x * multiplier,
                player.getDeltaMovement().y,
                player.getDeltaMovement().z * multiplier);
        player.hurtMarked = true;
    }

    public record Branch(int mastery, int choice) {
        public double progress() {
            return Math.max(0.0D, Math.min(1.0D, (mastery - 50) / 50.0D));
        }
    }
}
