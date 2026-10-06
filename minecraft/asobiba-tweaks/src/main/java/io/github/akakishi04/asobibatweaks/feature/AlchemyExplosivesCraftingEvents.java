package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Map;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.effect.MobEffect;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.PrimedTnt;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.alchemy.PotionContents;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;
import net.neoforged.neoforge.event.entity.player.ArrowLooseEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.level.BlockEvent;

public final class AlchemyExplosivesCraftingEvents {
    private static final String ARROW_PROFILE = "asobibatweaks_arrow_profile";
    private static final String NEXT_ARROW_PROFILE = "asobibatweaks_next_arrow_profile";

    @SubscribeEvent
    public void onRightClickBlock(PlayerInteractEvent.RightClickBlock event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND) return;

        if (AsobibaTweaksConfig.POTION_MIXING_ENABLED.getAsBoolean()
                && event.getLevel().getBlockState(event.getPos()).is(Blocks.CAULDRON)
                && isPotion(player.getMainHandItem())
                && isPotion(player.getOffhandItem())) {
            mixPotions(event, player);
            return;
        }

        if (AsobibaTweaksConfig.FLETCHING_TABLE_ENABLED.getAsBoolean()
                && event.getLevel().getBlockState(event.getPos()).is(Blocks.FLETCHING_TABLE)) {
            if (handleFletching(event, player)) return;
        }

        if (AsobibaTweaksConfig.TNT_DESIGN_ENABLED.getAsBoolean()
                && event.getLevel().getBlockState(event.getPos()).is(Blocks.TNT)) {
            if (tuneTnt(event, player)) return;
        }
    }

    @SubscribeEvent
    public void onBreak(BlockEvent.BreakEvent event) {
        if (!event.getState().is(Blocks.TNT)) return;
        if (event.getLevel() instanceof ServerLevel level) {
            TntDesignSavedData.get(level).remove(event.getPos().asLong());
        }
    }

    @SubscribeEvent
    public void onEntityJoin(EntityJoinLevelEvent event) {
        Entity entity = event.getEntity();

        if (entity instanceof PrimedTnt tnt && !event.getLevel().isClientSide()) {
            TntDesignSavedData designs = TntDesignSavedData.get((ServerLevel)event.getLevel());
            TntDesignSavedData.TntDesign design = designs.remove(tnt.blockPosition().asLong());
            if (design == null) {
                for (BlockPos pos : BlockPos.betweenClosed(tnt.blockPosition().offset(-1, -1, -1), tnt.blockPosition().offset(1, 1, 1))) {
                    design = designs.remove(pos.asLong());
                    if (design != null) break;
                }
            }
            if (design != null) {
                tnt.setFuse(design.fuse);
                tnt.getPersistentData().putFloat("asobibatweaks_tnt_power", design.power);
                tnt.getPersistentData().putBoolean("asobibatweaks_tnt_preserve_blocks", design.preserveBlocks);
                tnt.getPersistentData().putBoolean("asobibatweaks_tnt_fire", design.fire);
                tnt.getPersistentData().putDouble("asobibatweaks_tnt_wind", design.windMultiplier);
            }
        }

        if (entity instanceof AbstractArrow arrow
                && arrow.getOwner() instanceof ServerPlayer player
                && !event.getLevel().isClientSide()) {
            int profile = player.getPersistentData().getInt(NEXT_ARROW_PROFILE);
            if (profile != 0) {
                player.getPersistentData().remove(NEXT_ARROW_PROFILE);
                Vec3Scale.scaleArrow(arrow, profile);
            }
        }
    }

    @SubscribeEvent
    public void onArrowLoose(ArrowLooseEvent event) {
        if (!AsobibaTweaksConfig.FLETCHING_TABLE_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)) return;

        ItemStack ammo = player.getProjectile(event.getBow());
        int profile = arrowProfile(ammo);
        if (profile != 0) {
            player.getPersistentData().putInt(NEXT_ARROW_PROFILE, profile);
        }
    }

    private static void mixPotions(PlayerInteractEvent.RightClickBlock event, ServerPlayer player) {
        PotionContents a = player.getMainHandItem().get(DataComponents.POTION_CONTENTS);
        PotionContents b = player.getOffhandItem().get(DataComponents.POTION_CONTENTS);
        if (a == null || b == null || !a.hasEffects() || !b.hasEffects()) return;

        Map<Holder<MobEffect>, MobEffectInstance> merged = new LinkedHashMap<>();
        appendEffects(merged, a);
        appendEffects(merged, b);
        if (merged.isEmpty()) return;

        ItemStack result = new ItemStack(Items.POTION);
        result.set(DataComponents.POTION_CONTENTS,
                new PotionContents(java.util.Optional.empty(), java.util.Optional.empty(), new ArrayList<>(merged.values())));

        player.setItemInHand(InteractionHand.MAIN_HAND, result);
        player.setItemInHand(InteractionHand.OFF_HAND, new ItemStack(Items.GLASS_BOTTLE));
        player.displayClientMessage(Component.literal("Mixed potion created.").withStyle(ChatFormatting.LIGHT_PURPLE), true);
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    private static void appendEffects(Map<Holder<MobEffect>, MobEffectInstance> merged, PotionContents contents) {
        for (MobEffectInstance effect : contents.getAllEffects()) {
            int duration = Math.max(20, (int)Math.floor(effect.getDuration() * 0.60D));
            int amplifier = Math.max(0, effect.getAmplifier() - (effect.getAmplifier() > 0 ? 1 : 0));
            MobEffectInstance weakened = new MobEffectInstance(
                    effect.getEffect(), duration, amplifier, effect.isAmbient(), effect.isVisible(), effect.showIcon());
            MobEffectInstance previous = merged.get(effect.getEffect());
            if (previous == null || weakened.getDuration() > previous.getDuration()) {
                merged.put(effect.getEffect(), weakened);
            }
        }
    }

    private static boolean handleFletching(PlayerInteractEvent.RightClickBlock event, ServerPlayer player) {
        ItemStack main = player.getMainHandItem();
        ItemStack off = player.getOffhandItem();

        if (main.is(Items.ARROW) && off.is(Items.FEATHER)) {
            setArrowProfile(main, 1);
            if (!player.getAbilities().instabuild) off.shrink(1);
            player.displayClientMessage(Component.literal("Arrows tuned: lightweight").withStyle(ChatFormatting.AQUA), true);
            succeed(event);
            return true;
        }

        if (main.is(Items.ARROW) && off.is(Items.IRON_NUGGET)) {
            setArrowProfile(main, 2);
            if (!player.getAbilities().instabuild) off.shrink(1);
            player.displayClientMessage(Component.literal("Arrows tuned: heavyweight").withStyle(ChatFormatting.GRAY), true);
            succeed(event);
            return true;
        }

        if (main.is(Items.FLINT) && off.is(Items.FEATHER)) {
            int batches = 0;
            while (batches < 16
                    && (player.getAbilities().instabuild || (!main.isEmpty() && !off.isEmpty()))
                    && removeOne(player, Items.STICK)) {
                if (!player.getAbilities().instabuild) {
                    main.shrink(1);
                    off.shrink(1);
                }
                batches++;
            }
            if (batches <= 0) return false;

            ItemStack arrows = new ItemStack(Items.ARROW, batches * 4);
            if (!player.getInventory().add(arrows)) player.drop(arrows, false);
            player.displayClientMessage(Component.literal("Fletched " + (batches * 4) + " arrows.")
                    .withStyle(ChatFormatting.GREEN), true);
            succeed(event);
            return true;
        }

        return false;
    }

    private static boolean tuneTnt(PlayerInteractEvent.RightClickBlock event, ServerPlayer player) {
        ItemStack stack = player.getMainHandItem();
        TntDesignSavedData saved = TntDesignSavedData.get(player.serverLevel());
        TntDesignSavedData.TntDesign design = saved.getOrCreate(event.getPos().asLong());

        boolean changed = true;
        if (stack.is(Items.GUNPOWDER)) {
            design.power = Math.min(16.0F, design.power + 0.75F);
        } else if (stack.is(Items.STRING)) {
            design.fuse = Math.min(400, design.fuse + 20);
        } else if (stack.is(Items.REDSTONE)) {
            design.fuse = Math.max(5, design.fuse - 10);
        } else if (stack.is(Items.COBBLESTONE)) {
            design.preserveBlocks = true;
        } else if (stack.is(Items.BLAZE_POWDER)) {
            design.fire = true;
        } else if (stack.is(Items.FEATHER)) {
            design.windMultiplier = Math.min(4.0D, design.windMultiplier + 0.5D);
        } else {
            changed = false;
        }

        if (!changed) return false;
        saved.markDirty();
        if (!player.getAbilities().instabuild) stack.shrink(1);
        player.displayClientMessage(Component.literal(
                "TNT: power " + String.format(java.util.Locale.ROOT, "%.2f", design.power)
                        + ", fuse " + design.fuse
                        + (design.preserveBlocks ? ", blocks safe" : "")
                        + (design.fire ? ", incendiary" : "")
                        + ", wind x" + String.format(java.util.Locale.ROOT, "%.1f", design.windMultiplier)
        ).withStyle(ChatFormatting.GOLD), true);
        succeed(event);
        return true;
    }

    private static boolean removeOne(ServerPlayer player, net.minecraft.world.item.Item item) {
        if (player.getAbilities().instabuild) return true;
        for (int i = 0; i < player.getInventory().getContainerSize(); i++) {
            ItemStack stack = player.getInventory().getItem(i);
            if (stack.is(item)) {
                stack.shrink(1);
                return true;
            }
        }
        return false;
    }

    private static boolean isPotion(ItemStack stack) {
        return stack.is(Items.POTION) && stack.has(DataComponents.POTION_CONTENTS);
    }

    private static void setArrowProfile(ItemStack stack, int profile) {
        CompoundTag tag = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        tag.putInt(ARROW_PROFILE, profile);
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
    }

    private static int arrowProfile(ItemStack stack) {
        return stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag().getInt(ARROW_PROFILE);
    }


    private static void succeed(PlayerInteractEvent.RightClickBlock event) {
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    private static final class Vec3Scale {
        static void scaleArrow(AbstractArrow arrow, int profile) {
            if (profile == 1) {
                arrow.setDeltaMovement(arrow.getDeltaMovement().scale(1.18D));
                arrow.setBaseDamage(arrow.getBaseDamage() * 0.82D);
                arrow.getPersistentData().putString(ARROW_PROFILE, "light");
            } else if (profile == 2) {
                arrow.setDeltaMovement(arrow.getDeltaMovement().scale(0.82D));
                arrow.setBaseDamage(arrow.getBaseDamage() * 1.18D);
                arrow.getPersistentData().putString(ARROW_PROFILE, "heavy");
            }
            arrow.hurtMarked = true;
        }
    }
}
