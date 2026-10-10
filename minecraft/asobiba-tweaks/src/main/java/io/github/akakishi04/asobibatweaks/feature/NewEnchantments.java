package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;

/** Independent, datapack-backed enchantments; none depends on mastery or another feature. */
public final class NewEnchantments {
    public static final ResourceKey<Enchantment> ROOTED = key("rooted");
    public static final ResourceKey<Enchantment> OMINOUS = key("ominous");
    public static final ResourceKey<Enchantment> AFTERIMAGE = key("afterimage");
    public static final ResourceKey<Enchantment> AFTERIMAGE_DECOY = AFTERIMAGE;
    public static final ResourceKey<Enchantment> NOD = key("nod");

    private NewEnchantments() {}

    private static ResourceKey<Enchantment> key(String path) {
        return ResourceKey.create(Registries.ENCHANTMENT,
                ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, path));
    }

    public static int level(ItemStack stack, HolderLookup.Provider registries,
                            ResourceKey<Enchantment> key) {
        if (stack.isEmpty()) return 0;
        return registries.lookupOrThrow(Registries.ENCHANTMENT).get(key)
                .map(holder -> EnchantmentHelper.getItemEnchantmentLevel(holder, stack))
                .orElse(0);
    }

    public static boolean has(ItemStack stack, HolderLookup.Provider registries,
                              ResourceKey<Enchantment> key) {
        return level(stack, registries, key) > 0;
    }

    public static int equippedLevel(LivingEntity wearer, EquipmentSlot slot,
                                    ResourceKey<Enchantment> key) {
        return level(wearer.getItemBySlot(slot), wearer.registryAccess(), key);
    }

    public static boolean isIndependent(ResourceKey<Enchantment> key) {
        return ROOTED.equals(key) || OMINOUS.equals(key)
                || AFTERIMAGE.equals(key) || NOD.equals(key);
    }
}
