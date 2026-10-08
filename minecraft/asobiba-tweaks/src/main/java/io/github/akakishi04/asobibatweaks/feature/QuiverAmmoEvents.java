package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.ProjectileWeaponItem;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingGetProjectileEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/** Bridges selected Quiver ammunition and vanilla Bow/Crossbow loading. */
public final class QuiverAmmoEvents {
    private static final Map<ItemStack, PendingAmmo> PENDING = new WeakHashMap<>();

    @SubscribeEvent
    public void onGetProjectile(LivingGetProjectileEvent event) {
        if (!AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Player player)
                || !QuiverData.hasEquipped(player)) return;

        ItemStack weapon = event.getProjectileWeaponItemStack();
        if (!(weapon.getItem() instanceof ProjectileWeaponItem launcher)
                || !(weapon.is(Items.BOW) || weapon.is(Items.CROSSBOW))) return;

        int slot = QuiverData.selectedSlot(player);
        ItemStack selected = QuiverData.ammo(player, slot);
        if (selected.isEmpty() || !QuiverData.isAmmo(selected)
                || !(launcher.getSupportedHeldProjectiles(weapon).test(selected)
                        || launcher.getAllSupportedProjectiles(weapon).test(selected))) {
            // Invalid or empty selection: keep vanilla offhand/inventory fallback.
            return;
        }

        ItemStack temporary = selected.copy();
        event.setProjectileItemStack(temporary);
        if (player instanceof ServerPlayer serverPlayer) {
            PENDING.put(temporary, new PendingAmmo(serverPlayer, slot, selected.copy()));
        }
    }

    /**
     * Called after vanilla useAmmo has actually split the source or made it
     * intangible. Secondary Multishot copies have no pending-source identity.
     */
    public static void commitAmmoUse(ItemStack inputAfterVanilla) {
        PendingAmmo pending = PENDING.remove(inputAfterVanilla);
        if (pending == null || !AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()) return;

        int consumed = pending.original.getCount() - inputAfterVanilla.getCount();
        if (consumed <= 0) return;

        ItemStack currentlyStored = QuiverData.ammo(pending.owner, pending.slot);
        if (currentlyStored.isEmpty() || currentlyStored.getCount() < consumed
                || !ItemStack.isSameItemSameComponents(currentlyStored, pending.original)) {
            // Another action changed the slot. Do not remove unrelated ammo.
            return;
        }
        ItemStack remainder = currentlyStored.copy();
        remainder.shrink(consumed);
        QuiverData.setAmmo(pending.owner, pending.slot, remainder);
    }

    /** Vanilla Infinity matches all Items.ARROW, including enchanted copies. */
    public static int forceConsumableSpecialArrow(int vanilla, ItemStack weapon, ItemStack ammo,
                                                  boolean secondary, boolean creative) {
        if (vanilla != 0 || secondary || creative || isOrdinaryArrow(ammo)
                || !(weapon.is(Items.BOW) || weapon.is(Items.CROSSBOW))
                || !hasInfinity(weapon)) return vanilla;
        return 1;
    }

    public static boolean isOrdinaryArrow(ItemStack stack) {
        return stack.is(Items.ARROW)
                && ItemStack.isSameItemSameComponents(stack, new ItemStack(Items.ARROW));
    }

    /**
     * A fired vanilla Infinity arrow has INTANGIBLE_PROJECTILE temporarily
     * attached. This must not disqualify otherwise ordinary ammunition from
     * the Rapid Infinity streak, but other custom components still do.
     */
    public static boolean isOrdinaryShotProjectile(ItemStack projectile) {
        if (!projectile.is(Items.ARROW)) return false;
        ItemStack normalized = projectile.copy();
        normalized.remove(net.minecraft.core.component.DataComponents.INTANGIBLE_PROJECTILE);
        return isOrdinaryArrow(normalized);
    }

    private static boolean hasInfinity(ItemStack stack) {
        return EnchantmentMasteryData.enchantments(stack).entrySet().stream()
                .anyMatch(e -> e.getIntValue() > 0
                        && "minecraft:infinity".equals(EnchantmentMasteryData.id(e.getKey())));
    }

    @SubscribeEvent
    public void onLogin(PlayerEvent.PlayerLoggedInEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) QuiverNetworking.sendSnapshot(player);
    }

    @SubscribeEvent
    public void onRespawn(PlayerEvent.PlayerRespawnEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) QuiverNetworking.sendSnapshot(player);
    }

    @SubscribeEvent
    public void onChangedDimension(PlayerEvent.PlayerChangedDimensionEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) QuiverNetworking.sendSnapshot(player);
    }

    @SubscribeEvent
    public void onClone(PlayerEvent.Clone event) {
        CompoundTag previous = QuiverData.snapshot(event.getOriginal());
        if (!previous.isEmpty()) QuiverData.installSnapshot(event.getEntity(), previous);
    }

    @SubscribeEvent
    public void onFirstTick(PlayerTickEvent.Post event) {
        if (event.getEntity() instanceof ServerPlayer player && player.tickCount == 20) {
            // Retry once after the client Player entity has been initialized.
            QuiverNetworking.sendSnapshot(player);
        }
    }

    private record PendingAmmo(ServerPlayer owner, int slot, ItemStack original) {}
}
