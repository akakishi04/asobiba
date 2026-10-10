package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;

public final class QuiverMenuContainer implements Container {
    public static final int EQUIP_SLOT = 0;
    public static final int AMMO_START = 1;
    public static final int SIZE = 1 + QuiverData.AMMO_SLOTS;

    private final Player player;

    public QuiverMenuContainer(Player player) {
        this.player = player;
    }

    @Override
    public int getContainerSize() {
        return SIZE;
    }

    @Override
    public boolean isEmpty() {
        if (!QuiverData.equipped(player).isEmpty()) return false;
        for (int i = 0; i < QuiverData.AMMO_SLOTS; i++) {
            if (!QuiverData.ammo(player, i).isEmpty()) return false;
        }
        return true;
    }

    @Override
    public ItemStack getItem(int slot) {
        if (slot == EQUIP_SLOT) return QuiverData.equipped(player);
        int ammoSlot = slot - AMMO_START;
        return ammoSlot >= 0 && ammoSlot < QuiverData.AMMO_SLOTS
                ? QuiverData.ammo(player, ammoSlot)
                : ItemStack.EMPTY;
    }

    @Override
    public ItemStack removeItem(int slot, int amount) {
        if (amount <= 0) return ItemStack.EMPTY;

        ItemStack current = getItem(slot);
        if (current.isEmpty()) return ItemStack.EMPTY;

        if (slot == EQUIP_SLOT) {
            ItemStack removed = current.copy();
            QuiverData.setEquipped(player, ItemStack.EMPTY);
            return removed;
        }

        int ammoSlot = slot - AMMO_START;
        int take = Math.min(amount, current.getCount());
        ItemStack removed = current.copyWithCount(take);
        current.shrink(take);
        QuiverData.setAmmo(player, ammoSlot, current);
        return removed;
    }

    @Override
    public ItemStack removeItemNoUpdate(int slot) {
        ItemStack current = getItem(slot);
        if (current.isEmpty()) return ItemStack.EMPTY;

        ItemStack removed = current.copy();
        if (slot == EQUIP_SLOT) {
            QuiverData.setEquipped(player, ItemStack.EMPTY);
        } else {
            QuiverData.setAmmo(player, slot - AMMO_START, ItemStack.EMPTY);
        }
        return removed;
    }

    @Override
    public void setItem(int slot, ItemStack stack) {
        if (slot == EQUIP_SLOT) {
            if (stack.isEmpty() || QuiverData.isQuiver(stack)) {
                QuiverData.setEquipped(player, stack);
            }
            return;
        }

        int ammoSlot = slot - AMMO_START;
        if (ammoSlot < 0 || ammoSlot >= QuiverData.AMMO_SLOTS) return;
        if (stack.isEmpty() || QuiverData.isAmmo(stack)) {
            QuiverData.setAmmo(player, ammoSlot, stack);
        }
    }

    @Override
    public void setChanged() {
    }

    @Override
    public boolean stillValid(Player player) {
        return this.player == player;
    }

    @Override
    public void clearContent() {
        QuiverData.setEquipped(player, ItemStack.EMPTY);
    }

    @Override
    public boolean canPlaceItem(int slot, ItemStack stack) {
        if (!AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()) return false;
        if (slot == EQUIP_SLOT) return QuiverData.isQuiver(stack);
        return QuiverData.hasEquipped(player) && QuiverData.isAmmo(stack);
    }

    public Player player() {
        return player;
    }
}
