package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.List;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.dispenser.DefaultDispenseItemBehavior;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.item.PrimedTnt;
import net.minecraft.world.entity.monster.Creeper;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.entity.projectile.ThrownEnderpearl;
import net.minecraft.world.entity.vehicle.AbstractMinecart;
import net.minecraft.world.entity.vehicle.Boat;
import net.minecraft.world.item.AxeItem;
import net.minecraft.world.item.FishingRodItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.SwordItem;
import net.minecraft.world.item.alchemy.PotionContents;
import net.minecraft.world.item.alchemy.Potions;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DispenserBlock;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class InteractionTweaksEvents {
    private static boolean dispenserRegistered;

    public static void registerDispenserBehaviors() {
        if (dispenserRegistered) return;
        dispenserRegistered = true;

        DispenserBlock.registerBehavior(Items.ENDER_PEARL, new DefaultDispenseItemBehavior() {
            private final DefaultDispenseItemBehavior fallback = new DefaultDispenseItemBehavior();

            @Override
            protected ItemStack execute(net.minecraft.core.dispenser.BlockSource source, ItemStack stack) {
                if (!AsobibaTweaksConfig.DISPENSER_ENDER_PEARLS_ENABLED.getAsBoolean()) {
                    return fallback.dispense(source, stack);
                }

                ServerLevel level = source.level();
                Direction facing = source.state().getValue(DispenserBlock.FACING);
                Vec3 origin = Vec3.atCenterOf(source.pos())
                        .add(Vec3.atLowerCornerOf(facing.getNormal()).scale(0.7D));

                List<ServerPlayer> nearby = level.getEntitiesOfClass(
                        ServerPlayer.class,
                        new AABB(source.pos()).inflate(8.0D),
                        p -> !p.isSpectator()
                );
                if (nearby.size() != 1) {
                    return fallback.dispense(source, stack);
                }

                ServerPlayer owner = nearby.getFirst();
                ThrownEnderpearl pearl = new ThrownEnderpearl(level, owner);
                pearl.setPos(origin);
                pearl.shoot(facing.getStepX(), facing.getStepY() + 0.08D, facing.getStepZ(), 1.5F, 1.0F);
                level.addFreshEntity(pearl);
                stack.shrink(1);
                return stack;
            }
        });
    }

    @SubscribeEvent
    public void onRightClickBlock(PlayerInteractEvent.RightClickBlock event) {
        if (!AsobibaTweaksConfig.LINKED_DOUBLE_DOORS_ENABLED.getAsBoolean()
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND
                || event.getEntity().isShiftKeyDown()) return;

        BlockPos pos = event.getPos();
        BlockState state = event.getLevel().getBlockState(pos);
        if (!(state.getBlock() instanceof DoorBlock door)) return;

        boolean open = !state.getValue(DoorBlock.OPEN);
        door.setOpen(event.getEntity(), event.getLevel(), state, pos, open);

        for (Direction dir : Direction.Plane.HORIZONTAL) {
            BlockPos otherPos = pos.relative(dir);
            BlockState other = event.getLevel().getBlockState(otherPos);
            if (other.getBlock() == state.getBlock()
                    && other.getValue(DoorBlock.FACING) == state.getValue(DoorBlock.FACING)
                    && other.getValue(DoorBlock.HALF) == state.getValue(DoorBlock.HALF)
                    && other.getValue(DoorBlock.HINGE) != state.getValue(DoorBlock.HINGE)) {
                ((DoorBlock)other.getBlock()).setOpen(event.getEntity(), event.getLevel(), other, otherPos, open);
                break;
            }
        }

        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    @SubscribeEvent
    public void onRightClickItem(PlayerInteractEvent.RightClickItem event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND) return;

        ItemStack stack = event.getItemStack();

        if (AsobibaTweaksConfig.ENDER_PEARL_ANCHOR_ENABLED.getAsBoolean()
                && stack.is(Items.ENDER_PEARL)
                && player.isShiftKeyDown()) {
            handlePearlAnchor(event, player, stack);
            return;
        }

        if (AsobibaTweaksConfig.FIELD_REPAIR_ENABLED.getAsBoolean()
                && player.isShiftKeyDown()
                && stack.isDamageableItem()
                && tryFieldRepair(player, stack, player.getOffhandItem())) {
            event.setCancellationResult(InteractionResult.SUCCESS);
            event.setCanceled(true);
            return;
        }

        if (AsobibaTweaksConfig.TORCH_THROWING_ENABLED.getAsBoolean()
                && player.isShiftKeyDown()
                && stack.is(Items.TORCH)) {
            throwItem(player, stack, "asobibatweaks_thrown_torch", 1.15D);
            event.setCancellationResult(InteractionResult.SUCCESS);
            event.setCanceled(true);
            return;
        }

        if (AsobibaTweaksConfig.WEAPON_THROWING_ENABLED.getAsBoolean()
                && player.isShiftKeyDown()
                && (stack.getItem() instanceof SwordItem || stack.getItem() instanceof AxeItem)) {
            throwItem(player, stack, "asobibatweaks_thrown_weapon", 1.35D);
            event.setCancellationResult(InteractionResult.SUCCESS);
            event.setCanceled(true);
            return;
        }

        if (AsobibaTweaksConfig.EXPANDED_FISHING_ROD_ENABLED.getAsBoolean()
                && stack.getItem() instanceof FishingRodItem
                && player.fishing != null) {
            Vec3 target = player.getEyePosition();
            for (ItemEntity item : player.serverLevel().getEntitiesOfClass(
                    ItemEntity.class,
                    player.fishing.getBoundingBox().inflate(1.25D))) {
                Vec3 pull = target.subtract(item.position());
                if (pull.lengthSqr() > 0.01D) {
                    item.setDeltaMovement(item.getDeltaMovement().add(pull.normalize().scale(0.45D)));
                    item.hurtMarked = true;
                }
            }
        }
    }

    @SubscribeEvent
    public void onEntityInteract(PlayerInteractEvent.EntityInteract event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND) return;

        Entity target = event.getTarget();
        ItemStack held = event.getItemStack();

        if (AsobibaTweaksConfig.ARMOR_STAND_SWAP_ENABLED.getAsBoolean()
                && target instanceof ArmorStand stand
                && player.isShiftKeyDown()
                && held.isEmpty()) {
            for (EquipmentSlot slot : new EquipmentSlot[]{EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET}) {
                ItemStack playerStack = player.getItemBySlot(slot).copy();
                ItemStack standStack = stand.getItemBySlot(slot).copy();
                player.setItemSlot(slot, standStack);
                stand.setItemSlot(slot, playerStack);
            }
            player.displayClientMessage(Component.literal("Loadout swapped.").withStyle(ChatFormatting.AQUA), true);
            succeed(event);
            return;
        }

        if (AsobibaTweaksConfig.EXTINGUISH_CREEPERS_ENABLED.getAsBoolean()
                && target instanceof Creeper creeper
                && isWaterBottle(held)
                && (creeper.getSwellDir() > 0 || creeper.isIgnited())) {
            creeper.setSwellDir(-1);
            creeper.clearFire();
            if (!player.getAbilities().instabuild) {
                held.shrink(1);
                player.getInventory().add(new ItemStack(Items.GLASS_BOTTLE));
            }
            player.displayClientMessage(Component.literal("Fuse interrupted!").withStyle(ChatFormatting.AQUA), true);
            succeed(event);
            return;
        }

        if (AsobibaTweaksConfig.FIREWORK_PROPULSION_ENABLED.getAsBoolean()
                && held.is(Items.FIREWORK_ROCKET)
                && isPropulsionTarget(target)) {
            Vec3 direction = player.getLookAngle().normalize();
            target.setDeltaMovement(target.getDeltaMovement().add(direction.scale(1.25D)).add(0.0D, 0.18D, 0.0D));
            target.hurtMarked = true;
            if (!player.getAbilities().instabuild) held.shrink(1);
            succeed(event);
            return;
        }

        if (AsobibaTweaksConfig.EXPANDED_RIDING_ENABLED.getAsBoolean() && target instanceof Mob mob) {
            if (held.is(Items.SADDLE)
                    && !mob.getPersistentData().getBoolean("asobibatweaks_saddled")
                    && mob.getBbWidth() >= 0.75F
                    && mob.getBbHeight() >= 0.75F) {
                mob.getPersistentData().putBoolean("asobibatweaks_saddled", true);
                mob.setPersistenceRequired();
                if (!player.getAbilities().instabuild) held.shrink(1);
                succeed(event);
                return;
            }

            if (held.isEmpty()
                    && !player.isShiftKeyDown()
                    && mob.getPersistentData().getBoolean("asobibatweaks_saddled")
                    && !mob.isPassenger()
                    && !player.isPassenger()) {
                player.startRiding(mob, true);
                succeed(event);
                return;
            }
        }

        if (AsobibaTweaksConfig.CARRY_SMALL_MOBS_ENABLED.getAsBoolean()
                && target instanceof Mob mob
                && held.isEmpty()
                && player.isShiftKeyDown()
                && canCarry(player, mob)) {
            mob.startRiding(player, true);
            mob.getPersistentData().putBoolean("asobibatweaks_carried", true);
            mob.getPersistentData().putLong("asobibatweaks_carried_at", player.level().getGameTime());
            succeed(event);
        }
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) return;

        if (AsobibaTweaksConfig.EXPANDED_RIDING_ENABLED.getAsBoolean()
                && player.getVehicle() instanceof Mob mount
                && mount.getPersistentData().getBoolean("asobibatweaks_saddled")) {
            controlExpandedMount(player, mount);
        }

        if (!AsobibaTweaksConfig.CARRY_SMALL_MOBS_ENABLED.getAsBoolean()) return;

        boolean carrying = false;
        long now = player.level().getGameTime();
        for (Entity passenger : player.getPassengers()) {
            if (passenger instanceof Mob mob && mob.getPersistentData().getBoolean("asobibatweaks_carried")) {
                carrying = true;
                long carriedAt = mob.getPersistentData().getLong("asobibatweaks_carried_at");
                if (player.isShiftKeyDown() && now - carriedAt > 12L) {
                    mob.stopRiding();
                    mob.getPersistentData().remove("asobibatweaks_carried");
                }
            }
        }

        if (carrying) {
            Vec3 motion = player.getDeltaMovement();
            player.setDeltaMovement(motion.x * 0.86D, motion.y, motion.z * 0.86D);
        }
    }

    @SubscribeEvent
    public void onEntityTick(EntityTickEvent.Post event) {
        if (!(event.getEntity() instanceof ItemEntity item) || item.level().isClientSide()) return;

        if (item.getPersistentData().getBoolean("asobibatweaks_thrown_torch")) {
            if (item.onGround() || item.horizontalCollision) placeThrownTorch(item);
            return;
        }

        if (item.getPersistentData().getBoolean("asobibatweaks_thrown_weapon")
                && !item.getPersistentData().getBoolean("asobibatweaks_weapon_hit")
                && item.getDeltaMovement().lengthSqr() > 0.12D) {
            ServerPlayer owner = resolveOwner(item);
            if (owner == null) return;

            List<LivingEntity> hits = ((ServerLevel)item.level()).getEntitiesOfClass(
                    LivingEntity.class,
                    item.getBoundingBox().inflate(0.35D),
                    e -> e != owner && e.isAlive()
            );
            if (!hits.isEmpty()) {
                LivingEntity hit = hits.getFirst();
                float damage = (float)Math.min(10.0D, 4.0D + item.getDeltaMovement().length() * 3.0D);
                hit.hurt(owner.damageSources().playerAttack(owner), damage);
                ItemStack weapon = item.getItem();
                if (weapon.isDamageableItem()) {
                    weapon.setDamageValue(Math.min(weapon.getMaxDamage() - 1, weapon.getDamageValue() + 1));
                }
                item.getPersistentData().putBoolean("asobibatweaks_weapon_hit", true);
                item.setPickUpDelay(0);
                item.setDeltaMovement(item.getDeltaMovement().scale(0.2D));
            }
        }
    }

    private static void controlExpandedMount(ServerPlayer player, Mob mount) {
        float forward = player.zza;
        float strafe = player.xxa;
        if (Math.abs(forward) < 0.05F && Math.abs(strafe) < 0.05F) {
            Vec3 current = mount.getDeltaMovement();
            mount.setDeltaMovement(current.x * 0.82D, current.y, current.z * 0.82D);
            return;
        }

        Vec3 forwardVec = new Vec3(player.getLookAngle().x, 0.0D, player.getLookAngle().z);
        if (forwardVec.lengthSqr() < 0.001D) return;
        forwardVec = forwardVec.normalize();
        Vec3 right = new Vec3(-forwardVec.z, 0.0D, forwardVec.x);
        Vec3 desired = forwardVec.scale(forward).add(right.scale(strafe * 0.65D));
        if (desired.lengthSqr() > 1.0D) desired = desired.normalize();

        double speed = mount instanceof net.minecraft.world.entity.animal.goat.Goat ? 0.28D
                : mount instanceof net.minecraft.world.entity.animal.Pig ? 0.20D
                : mount instanceof net.minecraft.world.entity.animal.Cow ? 0.17D
                : mount instanceof net.minecraft.world.entity.animal.Sheep ? 0.16D
                : mount instanceof net.minecraft.world.entity.monster.Ravager ? 0.24D
                : 0.19D;

        Vec3 current = mount.getDeltaMovement();
        Vec3 target = desired.scale(speed);
        mount.setDeltaMovement(
                current.x * 0.55D + target.x * 0.45D,
                current.y,
                current.z * 0.55D + target.z * 0.45D
        );
        mount.setYRot(player.getYRot());
        mount.setYHeadRot(player.getYRot());
        mount.hurtMarked = true;
    }

    private static void handlePearlAnchor(PlayerInteractEvent.RightClickItem event, ServerPlayer player, ItemStack stack) {
        var data = player.getPersistentData();
        long now = player.level().getGameTime();
        long expiry = data.getLong("asobibatweaks_pearl_anchor_expiry");
        String dimension = data.getString("asobibatweaks_pearl_anchor_dimension");

        if (expiry >= now && dimension.equals(player.level().dimension().location().toString())) {
            player.teleportTo(
                    data.getDouble("asobibatweaks_pearl_anchor_x"),
                    data.getDouble("asobibatweaks_pearl_anchor_y"),
                    data.getDouble("asobibatweaks_pearl_anchor_z")
            );
            data.remove("asobibatweaks_pearl_anchor_expiry");
            data.remove("asobibatweaks_pearl_anchor_dimension");
            player.sendSystemMessage(Component.literal("Returned to the anchored pearl.").withStyle(ChatFormatting.LIGHT_PURPLE));
        } else {
            data.putDouble("asobibatweaks_pearl_anchor_x", player.getX());
            data.putDouble("asobibatweaks_pearl_anchor_y", player.getY());
            data.putDouble("asobibatweaks_pearl_anchor_z", player.getZ());
            data.putString("asobibatweaks_pearl_anchor_dimension", player.level().dimension().location().toString());
            data.putLong("asobibatweaks_pearl_anchor_expiry",
                    now + AsobibaTweaksConfig.ENDER_PEARL_ANCHOR_MINUTES.getAsInt() * 20L * 60L);
            if (!player.getAbilities().instabuild) stack.shrink(1);
            player.sendSystemMessage(Component.literal("Ender return point anchored.").withStyle(ChatFormatting.LIGHT_PURPLE));
        }

        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    private static boolean tryFieldRepair(ServerPlayer player, ItemStack tool, ItemStack material) {
        if (material.isEmpty() || !tool.isDamaged()) return false;

        String path = net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(tool.getItem()).getPath();
        boolean matches =
                (path.startsWith("wooden_") && material.is(ItemTags.PLANKS))
                || (path.startsWith("stone_") && material.is(Items.COBBLESTONE))
                || (path.startsWith("iron_") && material.is(Items.IRON_INGOT))
                || (path.startsWith("golden_") && material.is(Items.GOLD_INGOT))
                || (path.startsWith("diamond_") && material.is(Items.DIAMOND))
                || (path.startsWith("netherite_") && material.is(Items.NETHERITE_INGOT))
                || (path.startsWith("leather_") && material.is(Items.LEATHER))
                || (path.startsWith("chainmail_") && material.is(Items.IRON_NUGGET));

        if (!matches) return false;

        int repair = Math.max(1, tool.getMaxDamage() / 8);
        tool.setDamageValue(Math.max(0, tool.getDamageValue() - repair));
        if (!player.getAbilities().instabuild) material.shrink(1);
        player.displayClientMessage(Component.literal("Field repair: -" + repair + " damage").withStyle(ChatFormatting.GREEN), true);
        return true;
    }

    private static void throwItem(ServerPlayer player, ItemStack source, String tag, double speed) {
        ItemStack thrownStack = source.copyWithCount(1);
        if (!player.getAbilities().instabuild) source.shrink(1);

        Vec3 origin = player.getEyePosition().add(player.getLookAngle().scale(0.45D));
        ItemEntity thrown = new ItemEntity(player.level(), origin.x, origin.y, origin.z, thrownStack);
        thrown.setPickUpDelay(20);
        thrown.setDeltaMovement(player.getLookAngle().normalize().scale(speed).add(0.0D, 0.12D, 0.0D));
        thrown.getPersistentData().putBoolean(tag, true);
        thrown.getPersistentData().putString("asobibatweaks_throw_owner", player.getUUID().toString());
        player.level().addFreshEntity(thrown);
    }

    private static void placeThrownTorch(ItemEntity item) {
        BlockPos pos = item.blockPosition();
        if (!item.level().getBlockState(pos).canBeReplaced()) pos = pos.above();

        if (item.level().getBlockState(pos).canBeReplaced()
                && item.level().getBlockState(pos.below()).isFaceSturdy(item.level(), pos.below(), Direction.UP)) {
            item.level().setBlockAndUpdate(pos, Blocks.TORCH.defaultBlockState());
            item.discard();
        } else {
            item.getPersistentData().remove("asobibatweaks_thrown_torch");
            item.setPickUpDelay(0);
        }
    }

    private static ServerPlayer resolveOwner(ItemEntity item) {
        String ownerId = item.getPersistentData().getString("asobibatweaks_throw_owner");
        if (ownerId.isEmpty() || item.getServer() == null) return null;
        try {
            return item.getServer().getPlayerList().getPlayer(java.util.UUID.fromString(ownerId));
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    private static boolean isWaterBottle(ItemStack stack) {
        if (!stack.is(Items.POTION)) return false;
        PotionContents contents = stack.get(DataComponents.POTION_CONTENTS);
        return contents != null && contents.is(Potions.WATER);
    }

    private static boolean canCarry(ServerPlayer player, Mob mob) {
        if (mob.getBbWidth() > 1.25F || mob.getBbHeight() > 1.35F || mob.isPassenger() || mob.isVehicle()) return false;
        if (mob instanceof Enemy) {
            return UniversalBondData.isBonded(mob) && UniversalBondData.isOwner(mob, player.getUUID());
        }
        return true;
    }

    private static boolean isPropulsionTarget(Entity entity) {
        return entity instanceof Boat
                || entity instanceof AbstractMinecart
                || entity instanceof Mob
                || entity instanceof ItemEntity
                || entity instanceof PrimedTnt;
    }

    private static void succeed(PlayerInteractEvent.EntityInteract event) {
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }
}
