package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.BiomeTags;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.decoration.ItemFrame;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.vehicle.Boat;
import net.minecraft.world.entity.vehicle.ChestBoat;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class OceanAndDisplayEvents {
    public static final String LARGE_BOAT = "asobibatweaks_large_boat";
    private static final String RAFT_VISUAL = "asobibatweaks_raft_visual";
    private static final String RAFT_PARENT = "asobibatweaks_raft_parent";

    @SubscribeEvent
    public void onBoatInteract(PlayerInteractEvent.EntityInteract event) {
        if (!AsobibaTweaksConfig.LARGE_BOATS_ENABLED.getAsBoolean()
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND
                || !(event.getEntity() instanceof ServerPlayer player)
                || !(event.getTarget() instanceof ChestBoat boat)
                || !player.isShiftKeyDown()
                || !event.getItemStack().is(ItemTags.PLANKS)
                || boat.getPersistentData().getBoolean(LARGE_BOAT)) {
            return;
        }

        ItemStack planks = event.getItemStack();
        if (!player.getAbilities().instabuild && planks.getCount() < 4) {
            player.displayClientMessage(Component.literal("A cargo raft needs 4 planks.").withStyle(ChatFormatting.YELLOW), true);
            return;
        }

        if (!player.getAbilities().instabuild) planks.shrink(4);
        boat.getPersistentData().putBoolean(LARGE_BOAT, true);
        if (!boat.hasCustomName()) boat.setCustomName(Component.literal("Cargo Raft"));
        boat.refreshDimensions();
        spawnRaftVisual((ServerLevel)boat.level(), boat);
        player.displayClientMessage(Component.literal("Chest boat expanded into a cargo raft.").withStyle(ChatFormatting.AQUA), true);
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    @SubscribeEvent
    public void onEntityTick(EntityTickEvent.Post event) {
        if (event.getEntity().level().isClientSide()) return;

        if (event.getEntity() instanceof Display.BlockDisplay display
                && display.getPersistentData().getBoolean(RAFT_VISUAL)) {
            tickRaftVisual(display);
            return;
        }

        if (event.getEntity() instanceof Boat boat
                && AsobibaTweaksConfig.LARGE_BOATS_ENABLED.getAsBoolean()
                && boat.getPersistentData().getBoolean(LARGE_BOAT)) {
            int passengers = boat.getPassengers().size();
            int cargoStacks = 0;
            if (boat instanceof ChestBoat chestBoat) {
                for (int i = 0; i < chestBoat.getContainerSize(); i++) {
                    if (!chestBoat.getItem(i).isEmpty()) cargoStacks++;
                }
            }
            double drag = Math.max(0.965D, 0.995D - passengers * 0.004D - cargoStacks * 0.0008D);
            Vec3 movement = boat.getDeltaMovement();
            boat.setDeltaMovement(movement.x * drag, movement.y, movement.z * drag);
            if (boat.tickCount % 200 == Math.floorMod(boat.getId(), 200)
                    && !hasRaftVisual((ServerLevel)boat.level(), boat)) {
                spawnRaftVisual((ServerLevel)boat.level(), boat);
            }
        }

        if (event.getEntity() instanceof ItemFrame frame
                && AsobibaTweaksConfig.MAP_WALLS_ENABLED.getAsBoolean()
                && frame.tickCount % 20 == Math.floorMod(frame.getId(), 20)
                && frame.getItem().is(Items.FILLED_MAP)) {
            alignMapFrame(frame);
        }
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.OCEAN_DEBRIS_ENABLED.getAsBoolean()
                || player.tickCount % 200 != Math.floorMod(player.getId(), 200)
                || player.getRandom().nextDouble() > 0.018D
                || !player.level().getBiome(player.blockPosition()).is(BiomeTags.IS_OCEAN)) {
            return;
        }

        spawnDebris(player);
    }

    private static void spawnRaftVisual(ServerLevel level, Boat boat) {
        if (hasRaftVisual(level, boat)) return;

        CompoundTag tag = new CompoundTag();
        tag.putString("id", "minecraft:block_display");
        tag.put("block_state", NbtUtils.writeBlockState(Blocks.OAK_PLANKS.defaultBlockState()));

        CompoundTag transform = new CompoundTag();
        transform.put("translation", floats(-1.15F, -0.12F, -0.80F));
        transform.put("left_rotation", floats(0.0F, 0.0F, 0.0F, 1.0F));
        transform.put("scale", floats(2.30F, 0.16F, 1.60F));
        transform.put("right_rotation", floats(0.0F, 0.0F, 0.0F, 1.0F));
        tag.put("transformation", transform);
        tag.putFloat("view_range", 1.0F);
        tag.putFloat("shadow_radius", 0.0F);

        Entity entity = EntityType.loadEntityRecursive(tag, level, e -> e);
        if (!(entity instanceof Display.BlockDisplay display)) return;

        display.setPos(boat.getX(), boat.getY() + 0.20D, boat.getZ());
        display.setYRot(boat.getYRot());
        display.getPersistentData().putBoolean(RAFT_VISUAL, true);
        display.getPersistentData().putString(RAFT_PARENT, boat.getUUID().toString());
        level.addFreshEntity(display);
    }

    private static void tickRaftVisual(Display.BlockDisplay display) {
        if (!(display.level() instanceof ServerLevel level)) return;
        String id = display.getPersistentData().getString(RAFT_PARENT);
        if (id.isEmpty()) {
            display.discard();
            return;
        }

        Entity parent;
        try {
            parent = level.getEntity(java.util.UUID.fromString(id));
        } catch (IllegalArgumentException ex) {
            display.discard();
            return;
        }

        if (!(parent instanceof Boat boat) || !boat.isAlive()
                || !boat.getPersistentData().getBoolean(LARGE_BOAT)) {
            int missing = display.getPersistentData().getInt("asobibatweaks_raft_missing") + 1;
            display.getPersistentData().putInt("asobibatweaks_raft_missing", missing);
            if (missing > 100) display.discard();
            return;
        }

        display.getPersistentData().remove("asobibatweaks_raft_missing");
        display.setPos(boat.getX(), boat.getY() + 0.20D, boat.getZ());
        display.setYRot(boat.getYRot());
    }

    private static boolean hasRaftVisual(ServerLevel level, Boat boat) {
        return !level.getEntitiesOfClass(
                Display.BlockDisplay.class,
                boat.getBoundingBox().inflate(4.0D),
                d -> d.getPersistentData().getBoolean(RAFT_VISUAL)
                        && boat.getUUID().toString().equals(d.getPersistentData().getString(RAFT_PARENT))
        ).isEmpty();
    }

    private static ListTag floats(float... values) {
        ListTag list = new ListTag();
        for (float value : values) list.add(FloatTag.valueOf(value));
        return list;
    }

    private static void alignMapFrame(ItemFrame frame) {
        if (frame.getRotation() == 0) return;

        AABB nearby = frame.getBoundingBox().inflate(1.25D);
        boolean neighborMap = !frame.level().getEntitiesOfClass(
                ItemFrame.class,
                nearby,
                other -> other != frame
                        && other.getDirection() == frame.getDirection()
                        && other.getItem().is(Items.FILLED_MAP)
        ).isEmpty();

        if (neighborMap) frame.setRotation(0);
    }

    private static void spawnDebris(ServerPlayer player) {
        ServerLevel level = player.serverLevel();
        double angle = player.getRandom().nextDouble() * Math.PI * 2.0D;
        double distance = 14.0D + player.getRandom().nextDouble() * 18.0D;
        int x = (int)Math.floor(player.getX() + Math.cos(angle) * distance);
        int z = (int)Math.floor(player.getZ() + Math.sin(angle) * distance);
        int surface = level.getHeight(Heightmap.Types.WORLD_SURFACE, x, z);
        BlockPos water = new BlockPos(x, surface - 1, z);

        if (!level.getFluidState(water).is(net.minecraft.tags.FluidTags.WATER)) return;

        ItemStack stack = switch (player.getRandom().nextInt(10)) {
            case 0 -> new ItemStack(Items.BARREL);
            case 1 -> new ItemStack(Items.OAK_LOG, 1 + player.getRandom().nextInt(3));
            case 2 -> new ItemStack(Items.OAK_PLANKS, 2 + player.getRandom().nextInt(5));
            case 3 -> new ItemStack(Items.STICK, 2 + player.getRandom().nextInt(5));
            case 4 -> new ItemStack(Items.BOWL);
            case 5 -> new ItemStack(Items.LEATHER);
            case 6 -> new ItemStack(Items.ROTTEN_FLESH, 1 + player.getRandom().nextInt(3));
            case 7 -> new ItemStack(Items.IRON_NUGGET, 1 + player.getRandom().nextInt(4));
            case 8 -> new ItemStack(Items.STRING, 1 + player.getRandom().nextInt(3));
            default -> new ItemStack(Items.PAPER, 1 + player.getRandom().nextInt(3));
        };

        ItemEntity debris = new ItemEntity(level, x + 0.5D, surface + 0.08D, z + 0.5D, stack);
        debris.setDeltaMovement(
                (player.getRandom().nextDouble() - 0.5D) * 0.035D,
                0.0D,
                (player.getRandom().nextDouble() - 0.5D) * 0.035D
        );
        debris.getPersistentData().putBoolean("asobibatweaks_ocean_debris", true);
        debris.setExtendedLifetime();
        level.addFreshEntity(debris);
    }
}
