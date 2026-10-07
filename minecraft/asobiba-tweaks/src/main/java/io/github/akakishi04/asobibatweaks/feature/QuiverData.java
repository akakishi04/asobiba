package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.ItemContainerContents;

public final class QuiverData {
    public static final int AMMO_SLOTS = 9;

    private static final String ROOT = "asobibatweaks_quiver";
    private static final String EQUIPPED = "equipped";
    private static final String SELECTED = "selected";

    private QuiverData() {
    }

    public static ItemStack equipped(Player player) {
        CompoundTag root = root(player, false);
        if (!root.contains(EQUIPPED, Tag.TAG_COMPOUND)) return ItemStack.EMPTY;
        ItemStack stack = ItemStack.parseOptional(
                player.level().registryAccess(),
                root.getCompound(EQUIPPED)
        );
        return isQuiver(stack) ? stack : ItemStack.EMPTY;
    }

    public static boolean hasEquipped(Player player) {
        return !equipped(player).isEmpty();
    }

    public static void setEquipped(Player player, ItemStack stack) {
        CompoundTag root = root(player, true);
        if (stack == null || stack.isEmpty()) {
            root.remove(EQUIPPED);
            root.putInt(SELECTED, 0);
            return;
        }
        if (!isQuiver(stack)) return;

        root.put(EQUIPPED, stack.copyWithCount(1).saveOptional(player.level().registryAccess()));
        setSelectedSlot(player, selectedSlot(player));
    }

    public static int selectedSlot(Player player) {
        CompoundTag root = root(player, false);
        int selected = root.contains(SELECTED, Tag.TAG_INT) ? root.getInt(SELECTED) : 0;
        return Math.max(0, Math.min(AMMO_SLOTS - 1, selected));
    }

    public static void setSelectedSlot(Player player, int slot) {
        root(player, true).putInt(SELECTED, Math.max(0, Math.min(AMMO_SLOTS - 1, slot)));
    }

    public static ItemStack ammo(Player player, int slot) {
        if (slot < 0 || slot >= AMMO_SLOTS) return ItemStack.EMPTY;
        ItemStack quiver = equipped(player);
        if (quiver.isEmpty()) return ItemStack.EMPTY;

        ItemContainerContents contents = quiver.get(DataComponents.CONTAINER);
        if (contents == null || slot >= contents.getSlots()) return ItemStack.EMPTY;
        ItemStack stack = contents.getStackInSlot(slot);
        return isAmmo(stack) ? stack : ItemStack.EMPTY;
    }

    public static void setAmmo(Player player, int slot, ItemStack stack) {
        if (slot < 0 || slot >= AMMO_SLOTS) return;
        ItemStack quiver = equipped(player);
        if (quiver.isEmpty()) return;

        List<ItemStack> items = new ArrayList<>(AMMO_SLOTS);
        for (int i = 0; i < AMMO_SLOTS; i++) {
            items.add(ammoFromQuiver(quiver, i));
        }

        ItemStack accepted = stack == null || stack.isEmpty() || !isAmmo(stack)
                ? ItemStack.EMPTY
                : stack.copy();
        items.set(slot, accepted);

        quiver.set(DataComponents.CONTAINER, ItemContainerContents.fromItems(items));
        setEquipped(player, quiver);
    }

    public static ItemStack selectedAmmo(Player player) {
        return ammo(player, selectedSlot(player));
    }

    public static int cycleSelected(Player player, int direction) {
        if (!hasEquipped(player) || direction == 0) return selectedSlot(player);

        int current = selectedSlot(player);
        int step = direction > 0 ? 1 : -1;
        for (int offset = 1; offset <= AMMO_SLOTS; offset++) {
            int slot = Math.floorMod(current + offset * step, AMMO_SLOTS);
            ItemStack stack = ammo(player, slot);
            if (!stack.isEmpty() && isAmmo(stack)) {
                setSelectedSlot(player, slot);
                return slot;
            }
        }
        return current;
    }

    public static int nonEmptyAmmoSlots(Player player) {
        int count = 0;
        for (int slot = 0; slot < AMMO_SLOTS; slot++) {
            if (!ammo(player, slot).isEmpty()) count++;
        }
        return count;
    }

    public static boolean isAmmo(ItemStack stack) {
        return stack != null
                && !stack.isEmpty()
                && (stack.getItem() instanceof ArrowItem || stack.is(Items.FIREWORK_ROCKET));
    }

    public static boolean isQuiver(ItemStack stack) {
        return stack != null && !stack.isEmpty() && stack.is(AsobibaRegistries.QUIVER.get());
    }

    private static ItemStack ammoFromQuiver(ItemStack quiver, int slot) {
        ItemContainerContents contents = quiver.get(DataComponents.CONTAINER);
        if (contents == null || slot < 0 || slot >= contents.getSlots()) return ItemStack.EMPTY;
        ItemStack stack = contents.getStackInSlot(slot);
        return isAmmo(stack) ? stack : ItemStack.EMPTY;
    }

    private static CompoundTag root(Player player, boolean create) {
        CompoundTag persistent = player.getPersistentData();
        if (persistent.contains(ROOT, Tag.TAG_COMPOUND)) return persistent.getCompound(ROOT);
        if (!create) return new CompoundTag();

        CompoundTag root = new CompoundTag();
        root.putInt(SELECTED, 0);
        persistent.put(ROOT, root);
        return root;
    }
}
