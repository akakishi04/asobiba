package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.ChatFormatting;
import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.ResourceKey;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.ItemEnchantments;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.AnvilUpdateEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.living.LivingFallEvent;
import net.neoforged.neoforge.event.entity.player.AnvilRepairEvent;
import net.neoforged.neoforge.event.entity.player.ItemTooltipEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;

public final class EnchantmentTweaksEvents {
    private static final int BRANCH_THRESHOLD = 50;
    private static final String FORTUNE = "minecraft:fortune";
    private static final String SILK_TOUCH = "minecraft:silk_touch";

    @SubscribeEvent
    public void onBlockDrops(BlockDropsEvent event) {
        if (!(event.getBreaker() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;
        gain(player, player.getMainHandItem(), 1);
    }

    @SubscribeEvent
    public void onLivingDeath(LivingDeathEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;
        gain(player, player.getMainHandItem(), 4);
    }

    @SubscribeEvent
    public void onBreakSpeed(PlayerEvent.BreakSpeed event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;
        ItemStack stack = event.getEntity().getMainHandItem();
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!"minecraft:efficiency".equals(EnchantmentMasteryData.id(enchantment))) continue;
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery < BRANCH_THRESHOLD) return;
            int branch = EnchantmentMasteryData.getBranch(stack, enchantment);
            float factor = switch (branch) {
                case 0 -> 1.05F;
                case 1 -> 1.10F;
                default -> 1.075F;
            };
            event.setNewSpeed(event.getNewSpeed() * factor);
            return;
        }
    }

    @SubscribeEvent
    public void onFall(LivingFallEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;

        for (ItemStack armor : player.getArmorSlots()) {
            for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(armor).keySet()) {
                if (!"minecraft:feather_falling".equals(EnchantmentMasteryData.id(enchantment))) continue;
                int mastery = EnchantmentMasteryData.getMastery(armor, enchantment);
                if (mastery < BRANCH_THRESHOLD) continue;
                int branch = EnchantmentMasteryData.getBranch(armor, enchantment);
                if (branch == 0) {
                    event.setDistance(event.getDistance() * 0.85F);
                } else if (branch == 1 && event.getDistance() > 5.0F) {
                    for (LivingEntity other : player.level().getEntitiesOfClass(
                            LivingEntity.class, player.getBoundingBox().inflate(2.5D), e -> e != player)) {
                        other.push(other.getX() - player.getX(), 0.18D, other.getZ() - player.getZ());
                    }
                } else if (branch == 2) {
                    var motion = player.getDeltaMovement();
                    player.setDeltaMovement(motion.x * 1.12D, motion.y, motion.z * 1.12D);
                }
            }
        }
    }

    @SubscribeEvent
    public void onTooltip(ItemTooltipEvent event) {
        if (!AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;
        ItemStack stack = event.getItemStack();
        ItemEnchantments enchantments = EnchantmentMasteryData.enchantments(stack);
        if (enchantments.isEmpty()) return;

        boolean header = false;
        for (Holder<Enchantment> enchantment : enchantments.keySet()) {
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery <= 0) continue;
            if (!header) {
                event.getToolTip().add(Component.literal("Enchantment Mastery").withStyle(ChatFormatting.DARK_AQUA));
                header = true;
            }
            String name = enchantment.value().description().getString();
            String branch = mastery >= BRANCH_THRESHOLD
                    ? " / " + branchName(EnchantmentMasteryData.getBranch(stack, enchantment))
                    : "";
            ChatFormatting color = EnchantmentMasteryData.isCurse(enchantment)
                    ? ChatFormatting.DARK_RED : ChatFormatting.GRAY;
            event.getToolTip().add(Component.literal("  " + name + ": " + mastery + branch).withStyle(color));
        }

        String stored = EnchantmentMasteryData.storedExclusive(stack);
        if (!stored.isEmpty()) {
            event.getToolTip().add(Component.literal(
                    "Stored enchantment: " + stored + " " + EnchantmentMasteryData.storedExclusiveLevel(stack)
            ).withStyle(ChatFormatting.GOLD));
        }
    }

    @SubscribeEvent
    public void onEnchantingTable(PlayerEvent.PlayerLoggedInEvent event) {
        // Marker hook kept intentionally empty: mastery is item-local and needs no per-player migration.
    }

    @SubscribeEvent
    public void onRightClickBlock(net.neoforged.neoforge.event.entity.player.PlayerInteractEvent.RightClickBlock event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND
                || !player.isShiftKeyDown()
                || !event.getLevel().getBlockState(event.getPos()).is(Blocks.ENCHANTING_TABLE)) return;

        ItemStack stack = player.getMainHandItem();
        if (stack.isEmpty() || EnchantmentMasteryData.enchantments(stack).isEmpty()) return;

        if (AsobibaTweaksConfig.ENCHANTMENT_SWITCHING_ENABLED.getAsBoolean()
                && !EnchantmentMasteryData.storedExclusive(stack).isEmpty()) {
            if (toggleExclusive(player, stack)) {
                event.setCancellationResult(InteractionResult.SUCCESS);
                event.setCanceled(true);
                return;
            }
        }

        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !player.getOffhandItem().is(Items.LAPIS_LAZULI)) return;

        Holder<Enchantment> best = null;
        int bestMastery = BRANCH_THRESHOLD - 1;
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery > bestMastery) {
                best = enchantment;
                bestMastery = mastery;
            }
        }
        if (best == null) return;

        int branch = EnchantmentMasteryData.cycleBranch(stack, best);
        if (!player.getAbilities().instabuild) player.getOffhandItem().shrink(1);
        player.sendSystemMessage(Component.literal(
                best.value().description().getString() + " mastery branch -> " + branchName(branch)
        ).withStyle(ChatFormatting.AQUA));
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    @SubscribeEvent
    public void onAnvilUpdate(AnvilUpdateEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_SWITCHING_ENABLED.getAsBoolean()) return;
        ItemStack left = event.getLeft();
        ItemStack right = event.getRight();
        if (left.isEmpty() || right.isEmpty()) return;

        EnchantRef leftExclusive = findExclusive(left);
        EnchantRef rightExclusive = findExclusive(right);
        if (leftExclusive == null || rightExclusive == null || leftExclusive.id.equals(rightExclusive.id)) return;
        if (!isFortuneSilkPair(leftExclusive.id, rightExclusive.id)) return;

        ItemStack output = left.copy();
        EnchantmentMasteryData.storeExclusive(output, rightExclusive.id, rightExclusive.level);
        event.setOutput(output);
        event.setCost(Math.max(5L, event.getCost() + 5L));
        event.setMaterialCost(1);
    }

    @SubscribeEvent
    public void onAnvilRepair(AnvilRepairEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_INHERITANCE_ENABLED.getAsBoolean()) return;
        EnchantmentMasteryData.mergeInherited(event.getOutput(), event.getLeft(), event.getRight());
    }

    private static void gain(ServerPlayer player, ItemStack stack, int amount) {
        if (stack.isEmpty()) return;
        ItemEnchantments enchantments = EnchantmentMasteryData.enchantments(stack);
        if (enchantments.isEmpty()) return;

        for (Holder<Enchantment> enchantment : enchantments.keySet()) {
            boolean curse = EnchantmentMasteryData.isCurse(enchantment);
            if (curse && !AsobibaTweaksConfig.CURSE_GROWTH_ENABLED.getAsBoolean()) continue;
            EnchantmentMasteryData.addMastery(stack, enchantment, amount);

            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery == BRANCH_THRESHOLD && AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
                player.displayClientMessage(Component.literal(
                        enchantment.value().description().getString() + " can now choose a mastery branch at an enchanting table."
                ).withStyle(ChatFormatting.AQUA), true);
            }
            if ("minecraft:unbreaking".equals(EnchantmentMasteryData.id(enchantment))
                    && mastery >= 100
                    && stack.isDamaged()
                    && player.getRandom().nextDouble() < Math.min(0.08D, mastery / 5000.0D)) {
                stack.setDamageValue(Math.max(0, stack.getDamageValue() - 1));
            }
        }
    }

    private static boolean toggleExclusive(ServerPlayer player, ItemStack stack) {
        String storedId = EnchantmentMasteryData.storedExclusive(stack);
        int storedLevel = Math.max(1, EnchantmentMasteryData.storedExclusiveLevel(stack));
        EnchantRef active = findExclusive(stack);
        if (active == null || !isFortuneSilkPair(active.id, storedId)) return false;

        Holder<Enchantment> stored = holder(player, storedId);
        if (stored == null) return false;

        List<Holder<Enchantment>> toRemove = new ArrayList<>();
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (EnchantmentMasteryData.id(enchantment).equals(active.id)) toRemove.add(enchantment);
        }

        EnchantmentHelper.updateEnchantments(stack, mutable -> {
            mutable.removeIf(toRemove::contains);
            mutable.set(stored, storedLevel);
        });
        EnchantmentMasteryData.storeExclusive(stack, active.id, active.level);
        player.sendSystemMessage(Component.literal("Active enchantment -> " + stored.value().description().getString())
                .withStyle(ChatFormatting.GOLD));
        return true;
    }

    private static Holder<Enchantment> holder(ServerPlayer player, String id) {
        try {
            ResourceKey<Enchantment> key = ResourceKey.create(Registries.ENCHANTMENT, ResourceLocation.parse(id));
            return player.registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(key);
        } catch (RuntimeException ex) {
            return null;
        }
    }

    private static EnchantRef findExclusive(ItemStack stack) {
        for (var entry : EnchantmentMasteryData.enchantments(stack).entrySet()) {
            String id = EnchantmentMasteryData.id(entry.getKey());
            if (FORTUNE.equals(id) || SILK_TOUCH.equals(id)) {
                return new EnchantRef(id, entry.getIntValue());
            }
        }
        return null;
    }

    private static boolean isFortuneSilkPair(String a, String b) {
        return (FORTUNE.equals(a) && SILK_TOUCH.equals(b)) || (SILK_TOUCH.equals(a) && FORTUNE.equals(b));
    }

    private static String branchName(int branch) {
        return switch (branch) {
            case 0 -> "Precision";
            case 1 -> "Momentum";
            default -> "Endurance";
        };
    }

    private record EnchantRef(String id, int level) {}
}
