package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.Slot;
import net.minecraft.world.item.ItemStack;

public final class QuiverSlots {
    private QuiverSlots() {
    }

    public static final class EquipSlot extends Slot {
        private final Player player;

        public EquipSlot(QuiverMenuContainer container, int x, int y) {
            super(container, QuiverMenuContainer.EQUIP_SLOT, x, y);
            this.player = container.player();
        }

        @Override
        public boolean mayPlace(ItemStack stack) {
            return AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean() && QuiverData.isQuiver(stack);
        }

        @Override
        public int getMaxStackSize() {
            return 1;
        }

        @Override
        public boolean isActive() {
            return AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean();
        }
    }

    public static final class AmmoSlot extends Slot {
        private final Player player;

        public AmmoSlot(QuiverMenuContainer container, int ammoSlot, int x, int y) {
            super(container, QuiverMenuContainer.AMMO_START + ammoSlot, x, y);
            this.player = container.player();
        }

        @Override
        public boolean mayPlace(ItemStack stack) {
            return AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()
                    && QuiverData.hasEquipped(player)
                    && QuiverData.isAmmo(stack);
        }

        @Override
        public boolean isActive() {
            return AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()
                    && QuiverData.hasEquipped(player);
        }
    }
}
