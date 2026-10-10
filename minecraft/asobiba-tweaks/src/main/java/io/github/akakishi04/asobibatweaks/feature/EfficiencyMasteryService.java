package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.component.Tool;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;

/** Item-local Efficiency specializations; never changes harvesting eligibility. */
public final class EfficiencyMasteryService {
    private static final String RHYTHM = "asobibatweaks_efficiency_rhythm";
    private static final int WINDOW_TICKS = 30;
    private static final int MAX_STACKS = 5;
    private static final float HARDNESS_THRESHOLD = 3.0F;

    private EfficiencyMasteryService() {}

    static float speed(ItemStack stack, BlockState state, Level level,
                       BlockPos pos, float currentSpeed, long now) {
        Specialization spec = specialization(stack);
        if (spec == null || currentSpeed <= 0.0F
                || state.getDestroySpeed(level, pos) < 0.0F) return currentSpeed;
        double strength = Math.clamp((spec.mastery() - 50) / 50.0D, 0.0D, 1.0D);
        float raw = stack.getDestroySpeed(state);
        if (spec.branch() == 0) {
            if (!qualifies(stack, state, level, pos)
                    || state.getDestroySpeed(level, pos) < HARDNESS_THRESHOLD) return currentSpeed;
            return (float)(currentSpeed * (1.05D + 0.10D * strength));
        }
        if (spec.branch() == 1) {
            if (!qualifies(stack, state, level, pos)) return currentSpeed;
            int stacks = rhythmStacks(stack, level, now);
            return (float)(currentSpeed * (1.0D + stacks * (0.02D + 0.03D * strength)));
        }
        if (spec.branch() != 2 || raw <= 0.0F) return currentSpeed;
        Tool tool = stack.get(DataComponents.TOOL);
        if (tool == null) return currentSpeed;
        float preferred = tool.defaultMiningSpeed();
        for (Tool.Rule rule : tool.rules()) preferred = Math.max(preferred, rule.speed().orElse(0.0F));
        // Recover only a fraction of the tool's own lost base speed. Preserve
        // underwater/airborne/effect modifiers and never add harvest permission.
        if (!Float.isFinite(preferred) || preferred <= raw) return currentSpeed;
        double recovered = (preferred - raw) * (0.15D + 0.35D * strength);
        return (float)(currentSpeed * ((raw + recovered) / raw));
    }

    static void recordBreak(ItemStack stack, BlockState state, Level level,
                            BlockPos pos, long now) {
        Specialization spec = specialization(stack);
        if (spec == null || spec.branch() != 1 || !qualifies(stack, state, level, pos)) return;
        int stacks = Math.min(MAX_STACKS, rhythmStacks(stack, level, now) + 1);
        CompoundTag root = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        CompoundTag rhythm = new CompoundTag();
        rhythm.putInt("stacks", stacks);
        rhythm.putLong("last_break", now);
        rhythm.putString("dimension", level.dimension().location().toString());
        root.put(RHYTHM, rhythm);
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(root));
    }

    private static int rhythmStacks(ItemStack stack, Level level, long now) {
        CompoundTag rhythm = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY)
                .copyTag().getCompound(RHYTHM);
        long elapsed = now - rhythm.getLong("last_break");
        if (!rhythm.contains("last_break") || elapsed < 0L || elapsed > WINDOW_TICKS
                || !level.dimension().location().toString().equals(rhythm.getString("dimension"))) return 0;
        return Math.clamp(rhythm.getInt("stacks"), 0, MAX_STACKS);
    }

    private static boolean qualifies(ItemStack stack, BlockState state, Level level, BlockPos pos) {
        return state.getDestroySpeed(level, pos) > 0.0F && stack.getDestroySpeed(state) > 1.0F
                && (!state.requiresCorrectToolForDrops() || stack.isCorrectToolForDrops(state));
    }

    private static Specialization specialization(ItemStack stack) {
        for (var enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!"minecraft:efficiency".equals(EnchantmentMasteryData.id(enchantment))) continue;
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            int branch = EnchantmentMasteryData.getBranch(stack, enchantment);
            return mastery < 50 || branch < 0 || branch > 2 ? null
                    : new Specialization(branch, Math.min(100, mastery));
        }
        return null;
    }

    private record Specialization(int branch, int mastery) {}
}
