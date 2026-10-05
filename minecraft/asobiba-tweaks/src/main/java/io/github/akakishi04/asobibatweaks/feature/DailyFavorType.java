package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.block.CropBlock;
import net.minecraft.world.level.block.state.BlockState;

public enum DailyFavorType {
    MINING("Mining", "mine pickaxe blocks"),
    LOGGING("Logging", "break logs"),
    FARMING("Farming", "harvest crops"),
    HUNTING("Hunting", "defeat mobs");

    private final String displayName;
    private final String hint;

    DailyFavorType(String displayName, String hint) {
        this.displayName = displayName;
        this.hint = hint;
    }

    public String displayName() {
        return displayName;
    }

    public String hint() {
        return hint;
    }

    public boolean matchesBlock(BlockState state) {
        return switch (this) {
            case MINING -> state.is(BlockTags.MINEABLE_WITH_PICKAXE);
            case LOGGING -> state.is(BlockTags.LOGS);
            case FARMING -> state.getBlock() instanceof CropBlock;
            case HUNTING -> false;
        };
    }
}
