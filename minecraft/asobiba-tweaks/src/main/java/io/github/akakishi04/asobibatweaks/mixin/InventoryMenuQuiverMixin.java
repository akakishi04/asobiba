package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.QuiverData;
import io.github.akakishi04.asobibatweaks.feature.QuiverMenuContainer;
import io.github.akakishi04.asobibatweaks.feature.QuiverSlots;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.InventoryMenu;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(InventoryMenu.class)
public abstract class InventoryMenuQuiverMixin {
    @Inject(method = "<init>", at = @At("TAIL"))
    private void asobibatweaks$addQuiverSlots(
            Inventory inventory,
            boolean active,
            Player owner,
            CallbackInfo ci) {
        QuiverMenuContainer container = new QuiverMenuContainer(owner);
        AbstractContainerMenuAccessor accessor = (AbstractContainerMenuAccessor)(Object)this;

        accessor.asobibatweaks$addSlot(new QuiverSlots.EquipSlot(container, 178, 8));

        for (int ammo = 0; ammo < QuiverData.AMMO_SLOTS; ammo++) {
            int x = 178 + (ammo % 3) * 18;
            int y = 30 + (ammo / 3) * 18;
            accessor.asobibatweaks$addSlot(new QuiverSlots.AmmoSlot(container, ammo, x, y));
        }
    }
}
