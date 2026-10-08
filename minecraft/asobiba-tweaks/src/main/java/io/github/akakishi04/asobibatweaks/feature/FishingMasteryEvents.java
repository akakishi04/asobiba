package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.mixin.FishingHookTimingAccessor;
import net.minecraft.core.component.DataComponents;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.projectile.FishingHook;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.entity.player.ItemFishedEvent;

/**
 * Three Lure mastery paths. Adjust ONLY real live bobber timers and award
 * rhythm on a real fishing catch. No fish/treasure items are synthesized.
 */
public final class FishingMasteryEvents {
    private static final String RHYTHM_LAST = "asobibatweaks_lure_rhythm_last_catch";
    private static final String RHYTHM_COUNT = "asobibatweaks_lure_rhythm_catches";
    private static final String WINDOW_EXTENDED = "asobibatweaks_lure_window_extended";

    private static ItemStack activeRod(ServerPlayer player) {
        if (player.getMainHandItem().is(Items.FISHING_ROD)) return player.getMainHandItem();
        if (player.getOffhandItem().is(Items.FISHING_ROD)) return player.getOffhandItem();
        return ItemStack.EMPTY;
    }

    @SubscribeEvent
    public void onBobberTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof FishingHook hook)
                || hook.level().isClientSide()
                || !(hook.getPlayerOwner() instanceof ServerPlayer player)) return;

        ItemStack rod = activeRod(player);
        var branch = LauncherReloadMasteryEvents.branch(rod, "minecraft:lure");
        if (branch == null) return;

        FishingHookTimingAccessor timer = (FishingHookTimingAccessor)hook;
        double mastery = branch.progress();
        int wait = timer.asobibatweaks$getWaitingTicks();
        int nibble = timer.asobibatweaks$getBiteWindow();

        if (branch.choice() == 0 && wait > 20) {
            // Expected wait reduction 10%-30%. Additional tick probability
            // x/(1-x) produces the desired expected relative shortening.
            double reduction = 0.10D + 0.20D * mastery;
            if (player.getRandom().nextDouble() < reduction / (1.0D - reduction)) {
                timer.asobibatweaks$setWaitingTicks(wait - 1);
            }
        } else if (branch.choice() == 1) {
            // A bite is recognized by vanilla when nibble > 0. Extend it
            // once per episode; clearing the nibble rearms the next catch.
            var state = hook.getPersistentData();
            if (nibble <= 0) {
                state.remove(WINDOW_EXTENDED);
            } else if (!state.getBoolean(WINDOW_EXTENDED)) {
                int extension = (int)Math.round(nibble * (0.20D + 0.40D * mastery));
                timer.asobibatweaks$setBiteWindow(nibble + extension);
                state.putBoolean(WINDOW_EXTENDED, true);
            }
        } else if (branch.choice() == 2 && wait > 20) {
            CustomData data = rod.get(DataComponents.CUSTOM_DATA);
            if (data == null) return;
            long previous = data.copyTag().getLong(RHYTHM_LAST);
            int streak = data.copyTag().getInt(RHYTHM_COUNT);
            long now = player.level().getGameTime();
            if (streak <= 0 || now < previous || now - previous > 240L) return;

            double cap = 0.20D + 0.25D * mastery;
            double first = 0.10D;
            double effective = Math.min(cap, first + (streak - 1) * 0.08D);
            if (player.getRandom().nextDouble() < effective / (1.0D - effective)) {
                timer.asobibatweaks$setWaitingTicks(wait - 1);
            }
        }
    }

    public static void recordNetherCatch(ItemStack rod) {
        if (!AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;
        for (var enchantment : EnchantmentMasteryData.enchantments(rod).keySet()) {
            String id = EnchantmentMasteryData.id(enchantment);
            if ("minecraft:lure".equals(id) || "minecraft:luck_of_the_sea".equals(id)) {
                EnchantmentMasteryData.addMastery(rod, enchantment, 1);
            }
        }
    }

    @SubscribeEvent
    public void onActualCatch(ItemFishedEvent event) {
        if (event.isCanceled() || !(event.getEntity() instanceof ServerPlayer player)) return;
        ItemStack rod = activeRod(player);
        if (rod.isEmpty()) return;
        long now = player.level().getGameTime();
        for (var enchantment : EnchantmentMasteryData.enchantments(rod).keySet()) {
            String id = EnchantmentMasteryData.id(enchantment);
            if (!id.equals("minecraft:lure") && !id.equals("minecraft:luck_of_the_sea")) continue;
            if (AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) {
                EnchantmentMasteryData.addMastery(rod, enchantment, 1);
            }
        }

        var branch = LauncherReloadMasteryEvents.branch(rod, "minecraft:lure");
        if (branch == null || branch.choice() != 2) return;
        CustomData previous = rod.get(DataComponents.CUSTOM_DATA);
        long last = previous == null ? Long.MIN_VALUE
                : previous.copyTag().getLong(RHYTHM_LAST);
        int count = previous == null ? 0
                : previous.copyTag().getInt(RHYTHM_COUNT);
        int next = now >= last && now - last <= 240L
                ? Math.min(5, count + 1) : 1;
        CustomData.update(DataComponents.CUSTOM_DATA, rod, tag -> {
            tag.putLong(RHYTHM_LAST, now);
            tag.putInt(RHYTHM_COUNT, next);
        });
    }
}
