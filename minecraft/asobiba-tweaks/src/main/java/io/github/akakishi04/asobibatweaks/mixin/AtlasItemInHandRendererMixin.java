package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.client.renderer.ItemInHandRenderer;
import net.minecraft.core.component.DataComponents;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(ItemInHandRenderer.class)
public abstract class AtlasItemInHandRendererMixin {
    @Redirect(
            method = "renderArmWithItem",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/minecraft/world/item/ItemStack;is(Lnet/minecraft/world/item/Item;)Z",
                    ordinal = 0
            )
    )
    private boolean asobibatweaks$renderAtlasAsFilledMap(ItemStack stack, Item testedItem) {
        if (testedItem == Items.FILLED_MAP
                && AsobibaTweaksConfig.ATLAS_ENABLED.getAsBoolean()
                && stack.is(AsobibaRegistries.ATLAS.get())
                && stack.has(DataComponents.MAP_ID)) {
            return true;
        }
        return stack.is(testedItem);
    }
}
