package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.core.Holder;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.enchantment.Enchantment;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/**
 * Applies Unbreaking mastery after vanilla EnchantmentHelper has already decided
 * how much durability is actually lost. No durability is ever awarded by this code.
 *
 * Per-item runtime state lives inside CUSTOM_DATA and therefore follows the exact
 * enchanted stack across save/reload, trading, storage and item transfers.
 */
public final class UnbreakingMasteryEvents {
    private static final String UNBREAKING = "minecraft:unbreaking";
    private static final String RUNTIME = "asobibatweaks_unbreaking_runtime";
    private static final int MAX_ROLLS_PER_CALL = 128;
    private static final Map<ServerPlayer, HandState> OBSERVED_HANDS = new WeakHashMap<>();

    /**
     * Called on the server by the ItemStack mixin, after the normal Unbreaking roll.
     * A zero post-vanilla cost still counts as using the item for streak/idle tracking.
     */
    public static int adjustDurability(ItemStack stack, ServerLevel level, LivingEntity holder, int postVanilla) {
        if (!(holder instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !stack.isDamageableItem() || postVanilla < 0) {
            return postVanilla;
        }

        Branch selected = branch(stack);
        if (selected == null) return postVanilla;

        long now = level.getGameTime();
        CompoundTag root = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        CompoundTag state = root.getCompound(RUNTIME);
        if (!state.contains("branch") || state.getInt("branch") != selected.index()
                || !state.contains("last_tick") || now < state.getLong("last_tick")) {
            state = new CompoundTag();
            state.putInt("branch", selected.index());
            state.putLong("last_tick", now);
        }

        double strength = (Math.min(100, selected.mastery()) - 50) / 50.0D;
        int cost = postVanilla;
        long lastUse = state.getLong("last_tick");

        if (selected.index() == 0) {
            // Idle-time recharge; the first use starts the clock, not free charges.
            int capacity = 1 + (int)Math.round(2.0D * strength);
            long interval = Math.round(400.0D - 200.0D * strength);
            int charges = Math.min(capacity, Math.max(0, state.getInt("reserve")));
            long elapsed = now - lastUse;
            if (elapsed >= interval) {
                charges = Math.min(capacity, charges + (int)Math.min(capacity, elapsed / interval));
            }
            int saved = Math.min(charges, cost);
            cost -= saved;
            state.putInt("reserve", charges - saved);
        } else if (selected.index() == 1) {
            // Consecutive uses ramp over ten events and expire after three seconds.
            int previousStreak = now - lastUse <= 60L ? state.getInt("streak") : 0;
            int streak = Math.min(10, Math.max(0, previousStreak) + 1);
            double chance = (0.05D + 0.10D * strength) * (streak / 10.0D);
            cost -= savedByRolls(player, cost, chance);
            state.putInt("streak", streak);
        } else if (selected.index() == 2 && protectiveActive(stack, selected)) {
            double chance = 0.30D + 0.30D * strength;
            cost -= savedByRolls(player, cost, chance);
        }

        state.putLong("last_tick", now);
        root.put(RUNTIME, state);
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(root));
        return Math.max(0, cost);
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) return;
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            OBSERVED_HANDS.remove(player);
            return;
        }

        ItemStack main = player.getMainHandItem();
        ItemStack off = player.getOffhandItem();
        HandState previous = OBSERVED_HANDS.get(player);
        if (previous == null) {
            OBSERVED_HANDS.put(player, new HandState(main, off));
            resetContinuousStreak(main);
            resetContinuousStreak(off);
            return;
        }
        if (previous.main != main) {
            resetContinuousStreak(previous.main);
            resetContinuousStreak(main);
            previous.main = main;
        }
        if (previous.off != off) {
            resetContinuousStreak(previous.off);
            resetContinuousStreak(off);
            previous.off = off;
        }
    }

    @SubscribeEvent
    public void onBreakSpeed(PlayerEvent.BreakSpeed event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;
        // Break speed is queried on both logical sides; apply the same modifier
        // on client and server to avoid misleading progress bars.
        if (isProtective(event.getEntity().getMainHandItem())) {
            event.setNewSpeed(event.getNewSpeed() * 0.90F);
        }
    }

    @SubscribeEvent
    public void onAttack(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getAmount() <= 0.0F
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            return;
        }
        ItemStack sourceWeapon = event.getSource().getWeaponItem();
        if (sourceWeapon == null || sourceWeapon.isEmpty()) {
            if (event.getSource().getDirectEntity() != player) return;
            sourceWeapon = player.getMainHandItem();
        }
        if (isProtective(sourceWeapon)) {
            event.setAmount(event.getAmount() * 0.90F);
        }
    }

    @SubscribeEvent
    public void onArmorPerformance(LivingDamageEvent.Pre event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.getNewDamage() <= 0.0F
                || event.getSource().is(DamageTypeTags.BYPASSES_ARMOR)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            return;
        }
        for (ItemStack piece : player.getArmorSlots()) {
            if (isProtective(piece)) {
                // One bounded protection trade-off, not 10% compounded per piece.
                event.setNewDamage(event.getNewDamage() * 1.10F);
                return;
            }
        }
    }

    private static int savedByRolls(ServerPlayer player, int damage, double chance) {
        int saved = 0;
        for (int i = 0, rolls = Math.min(damage, MAX_ROLLS_PER_CALL); i < rolls; ++i) {
            if (player.getRandom().nextDouble() < chance) saved++;
        }
        return saved;
    }

    private static boolean isProtective(ItemStack stack) {
        Branch selected = branch(stack);
        return selected != null && selected.index() == 2 && protectiveActive(stack, selected);
    }

    private static boolean protectiveActive(ItemStack stack, Branch selected) {
        if (!stack.isDamageableItem() || stack.getMaxDamage() <= 0) return false;
        double strength = (Math.min(100, selected.mastery()) - 50) / 50.0D;
        double remaining = (stack.getMaxDamage() - stack.getDamageValue()) / (double)stack.getMaxDamage();
        return remaining <= 0.15D + 0.10D * strength;
    }

    private static Branch branch(ItemStack stack) {
        if (stack.isEmpty()) return null;
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!UNBREAKING.equals(EnchantmentMasteryData.id(enchantment))) continue;
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            int index = EnchantmentMasteryData.getBranch(stack, enchantment);
            return mastery >= 50 && index >= 0 && index <= 2 ? new Branch(mastery, index) : null;
        }
        return null;
    }

    private static void resetContinuousStreak(ItemStack stack) {
        Branch selected = branch(stack);
        if (selected == null || selected.index() != 1) return;
        CompoundTag root = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        CompoundTag state = root.getCompound(RUNTIME);
        if (state.getInt("branch") != 1 || state.getInt("streak") == 0) return;
        state.putInt("streak", 0);
        root.put(RUNTIME, state);
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(root));
    }

    private static final class HandState {
        private ItemStack main;
        private ItemStack off;

        private HandState(ItemStack main, ItemStack off) {
            this.main = main;
            this.off = off;
        }
    }

    private record Branch(int mastery, int index) {}
}
