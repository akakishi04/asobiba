package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.entity.NetherFishEntity;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.FishingRodItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDropsEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class NetherFishingEvents {
    private static final String HEAT_TREATED = "asobibatweaks_lava_fishing_rod";
    private static final String CATCH_AT = "asobibatweaks_lava_catch_at";
    private static final String CATCH_X = "asobibatweaks_lava_catch_x";
    private static final String CATCH_Y = "asobibatweaks_lava_catch_y";
    private static final String CATCH_Z = "asobibatweaks_lava_catch_z";

    @SubscribeEvent
    public void onUse(PlayerInteractEvent.RightClickItem event) {
        if (!AsobibaTweaksConfig.NETHER_FISHING_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND
                || !(event.getItemStack().getItem() instanceof FishingRodItem)) {
            return;
        }

        ItemStack rod = event.getItemStack();
        ItemStack offhand = player.getOffhandItem();

        if (player.isShiftKeyDown() && offhand.is(Items.MAGMA_CREAM) && !isHeatTreated(rod)) {
            CompoundTag root = rod.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
            root.putBoolean(HEAT_TREATED, true);
            rod.set(DataComponents.CUSTOM_DATA, CustomData.of(root));
            if (!player.getAbilities().instabuild) offhand.shrink(1);
            player.sendSystemMessage(Component.literal("The fishing rod is now heat-treated.")
                    .withStyle(ChatFormatting.GOLD));
            event.setCancellationResult(InteractionResult.SUCCESS);
            event.setCanceled(true);
            return;
        }

        if (!isHeatTreated(rod)) return;

        HitResult hit = player.pick(24.0D, 0.0F, false);
        if (!(hit instanceof BlockHitResult blockHit)
                || !player.level().getFluidState(blockHit.getBlockPos()).is(FluidTags.LAVA)) {
            return;
        }

        long now = player.level().getGameTime();
        player.getPersistentData().putLong(CATCH_AT, now + 60L + player.getRandom().nextInt(101));
        player.getPersistentData().putInt(CATCH_X, blockHit.getBlockPos().getX());
        player.getPersistentData().putInt(CATCH_Y, blockHit.getBlockPos().getY());
        player.getPersistentData().putInt(CATCH_Z, blockHit.getBlockPos().getZ());
        player.displayClientMessage(Component.literal("The line sinks into the lava...").withStyle(ChatFormatting.DARK_RED), true);

        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.NETHER_FISHING_ENABLED.getAsBoolean()) return;

        long now = player.level().getGameTime();
        long catchAt = player.getPersistentData().getLong(CATCH_AT);
        if (catchAt > 0L && now >= catchAt) finishCatch(player);

        if (AsobibaTweaksConfig.NETHER_FISH_ENABLED.getAsBoolean()
                && player.level().dimension() == Level.NETHER
                && player.tickCount % 300 == Math.floorMod(player.getId(), 300)
                && player.getRandom().nextDouble() < 0.08D) {
            tryNaturalSpawn(player);
        }
    }

    @SubscribeEvent
    public void onDrops(LivingDropsEvent event) {
        if (!(event.getEntity() instanceof NetherFishEntity fish)) return;

        Item item = fish.getType() == AsobibaRegistries.LAVA_MINNOW.get()
                ? AsobibaRegistries.LAVA_MINNOW_ITEM.get()
                : fish.getType() == AsobibaRegistries.EMBERFIN.get()
                ? AsobibaRegistries.EMBERFIN_ITEM.get()
                : AsobibaRegistries.BASALT_EEL_ITEM.get();

        event.getDrops().add(new ItemEntity(
                fish.level(), fish.getX(), fish.getY(), fish.getZ(), new ItemStack(item)
        ));
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        var data = event.getEntity().getPersistentData();
        data.remove(CATCH_AT);
    }

    private static void finishCatch(ServerPlayer player) {
        var data = player.getPersistentData();
        data.remove(CATCH_AT);

        BlockPos pos = new BlockPos(data.getInt(CATCH_X), data.getInt(CATCH_Y), data.getInt(CATCH_Z));
        if (player.distanceToSqr(pos.getCenter()) > 24.0D * 24.0D
                || !player.level().getFluidState(pos).is(FluidTags.LAVA)
                || !isHeatTreated(player.getMainHandItem())) {
            player.displayClientMessage(Component.literal("The lava line went slack.").withStyle(ChatFormatting.GRAY), true);
            return;
        }

        ItemStack catchStack;
        int roll = player.getRandom().nextInt(100);
        if (roll < 32) catchStack = new ItemStack(AsobibaRegistries.LAVA_MINNOW_ITEM.get());
        else if (roll < 54) catchStack = new ItemStack(AsobibaRegistries.EMBERFIN_ITEM.get());
        else if (roll < 66) catchStack = new ItemStack(AsobibaRegistries.BASALT_EEL_ITEM.get());
        else if (roll < 76) catchStack = new ItemStack(Items.QUARTZ, 1 + player.getRandom().nextInt(3));
        else if (roll < 84) catchStack = new ItemStack(Items.GOLD_NUGGET, 2 + player.getRandom().nextInt(5));
        else if (roll < 91) catchStack = new ItemStack(Items.BONE);
        else if (roll < 97) catchStack = new ItemStack(Items.STRING, 1 + player.getRandom().nextInt(2));
        else catchStack = new ItemStack(Items.MAGMA_CREAM);

        if (!player.getInventory().add(catchStack)) player.drop(catchStack, false);

        ItemStack rod = player.getMainHandItem();
        if (rod.isDamageableItem() && !player.getAbilities().instabuild) {
            rod.hurtAndBreak(1, player, net.minecraft.world.entity.EquipmentSlot.MAINHAND);
        }
        player.displayClientMessage(Component.literal("Something bit the lava line!").withStyle(ChatFormatting.GOLD), true);
    }

    private static void tryNaturalSpawn(ServerPlayer player) {
        ServerLevel level = player.serverLevel();
        if (level.getEntitiesOfClass(NetherFishEntity.class, player.getBoundingBox().inflate(32.0D)).size() >= 12) {
            return;
        }

        for (int attempt = 0; attempt < 18; attempt++) {
            BlockPos pos = player.blockPosition().offset(
                    player.getRandom().nextInt(41) - 20,
                    player.getRandom().nextInt(17) - 8,
                    player.getRandom().nextInt(41) - 20
            );
            if (!level.getFluidState(pos).is(FluidTags.LAVA)) continue;

            EntityType<NetherFishEntity> type = switch (player.getRandom().nextInt(10)) {
                case 0, 1 -> AsobibaRegistries.BASALT_EEL.get();
                case 2, 3, 4 -> AsobibaRegistries.EMBERFIN.get();
                default -> AsobibaRegistries.LAVA_MINNOW.get();
            };
            int group = type == AsobibaRegistries.LAVA_MINNOW.get() ? 2 + player.getRandom().nextInt(3) : 1;
            for (int i = 0; i < group; i++) {
                NetherFishEntity fish = type.create(level);
                if (fish == null) continue;
                fish.moveTo(
                        pos.getX() + 0.5D + (player.getRandom().nextDouble() - 0.5D),
                        pos.getY() + 0.5D,
                        pos.getZ() + 0.5D + (player.getRandom().nextDouble() - 0.5D),
                        player.getRandom().nextFloat() * 360.0F,
                        0.0F
                );
                level.addFreshEntity(fish);
            }
            return;
        }
    }

    private static boolean isHeatTreated(ItemStack stack) {
        if (!(stack.getItem() instanceof FishingRodItem)) return false;
        return stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY)
                .copyTag()
                .getBoolean(HEAT_TREATED);
    }
}
