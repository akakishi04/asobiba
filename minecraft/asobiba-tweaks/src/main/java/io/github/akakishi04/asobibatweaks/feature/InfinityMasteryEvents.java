package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.core.Holder;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantment;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingGetProjectileEvent;

/**
 * Infinity mastery has exactly three side-grade branches:
 * a seedless ordinary arrow, repeated normal-arrow firing durability savings,
 * or a carefully aimed full-charge shot durability saving.
 *
 * The standard ammo-use enchantment still decides whether an arrow is
 * consumed. In particular, this class never makes tipped, spectral or
 * enchanted arrows free.
 */
public final class InfinityMasteryEvents {
    private static final String INFINITY = "minecraft:infinity";
    private static final Map<ItemStack, ShotState> RECENT_SHOTS = new WeakHashMap<>();

    @SubscribeEvent
    public void onGetProjectile(LivingGetProjectileEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof net.minecraft.world.entity.player.Player)
                || !event.getProjectileItemStack().isEmpty()) {
            return;
        }

        ItemStack launcher = event.getProjectileWeaponItemStack();
        if (!isLauncher(launcher)) return;

        Branch selected = branch(launcher);
        if (selected != null && selected.index() == 0) {
            // A brand-new ordinary Arrow ItemStack; never synthesize special ammo.
            // Vanilla Infinity ammo-use handles its intangible/non-pickup state.
            event.setProjectileItemStack(new ItemStack(Items.ARROW));
        }
    }

    /**
     * Runs once per projectile group, before the launcher takes its ordinary
     * durability cost. The projectile count (Multishot) is not a shot streak.
     */
    public static void recordShot(ServerLevel level, LivingEntity shooter, ItemStack weapon,
                                  List<ItemStack> projectiles, float velocity) {
        if (!(shooter instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !isLauncher(weapon)
                || projectiles.isEmpty()) {
            return;
        }

        Branch selected = branch(weapon);
        if (selected == null || selected.index() == 0) {
            RECENT_SHOTS.remove(weapon);
            return;
        }

        long now = level.getGameTime();
        ShotState previous = RECENT_SHOTS.get(weapon);
        double growth = Math.max(0.0D, Math.min(1.0D, (selected.mastery() - 50) / 50.0D));

        if (selected.index() == 1) {
            boolean ordinary = projectiles.stream().anyMatch(QuiverAmmoEvents::isOrdinaryArrow);
            if (!ordinary) {
                RECENT_SHOTS.remove(weapon);
                return;
            }

            int streak = previous != null && previous.branch == 1
                    && now >= previous.lastShot && now - previous.lastShot <= 80L
                    ? Math.min(3, previous.streak + 1) : 1;
            double chance = streak >= 3 ? 0.10D + 0.25D * growth : 0.0D;
            RECENT_SHOTS.put(weapon, new ShotState(
                    now, streak, 1, chance > 0.0D && player.getRandom().nextDouble() < chance
            ));
        } else if (selected.index() == 2) {
            boolean fullyCharged = weapon.is(Items.CROSSBOW) || velocity >= 2.85F;
            double chance = 0.15D + 0.35D * growth;
            RECENT_SHOTS.put(weapon, new ShotState(
                    now, 0, 2, fullyCharged && player.getRandom().nextDouble() < chance
            ));
        }
    }

    /**
     * Called after normal Unbreaking durability processing. Do not create
     * negative durability costs or refund already-broken items.
     */
    public static int adjustDurability(ItemStack weapon, ServerLevel level,
                                       LivingEntity wearer, int postVanilla) {
        if (!(wearer instanceof ServerPlayer)
                || postVanilla <= 0
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            return postVanilla;
        }

        ShotState state = RECENT_SHOTS.get(weapon);
        if (state == null || state.lastShot != level.getGameTime() || !state.saveDurability) {
            return postVanilla;
        }
        // One proc negates the wear attributable to a single shot group.
        return 0;
    }

    private static Branch branch(ItemStack weapon) {
        if (weapon.isEmpty()) return null;
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(weapon).keySet()) {
            if (!INFINITY.equals(EnchantmentMasteryData.id(enchantment))) continue;
            int mastery = EnchantmentMasteryData.getMastery(weapon, enchantment);
            int index = EnchantmentMasteryData.getBranch(weapon, enchantment);
            return mastery >= 50 && index >= 0 && index <= 2 ? new Branch(mastery, index) : null;
        }
        return null;
    }

    private static boolean isLauncher(ItemStack stack) {
        return stack.is(Items.BOW) || stack.is(Items.CROSSBOW);
    }

    private record Branch(int mastery, int index) {}

    private record ShotState(long lastShot, int streak, int branch, boolean saveDurability) {}
}
