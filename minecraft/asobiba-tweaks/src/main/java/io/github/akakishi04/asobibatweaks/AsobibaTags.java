package io.github.akakishi04.asobibatweaks;

import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.TagKey;
import net.minecraft.world.item.enchantment.Enchantment;

public final class AsobibaTags {
    public static final TagKey<Enchantment> ARCANE_BOOKSHELF_POOL =
            TagKey.create(Registries.ENCHANTMENT,
                    ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "arcane_bookshelf_pool"));

    private AsobibaTags() {}
}
