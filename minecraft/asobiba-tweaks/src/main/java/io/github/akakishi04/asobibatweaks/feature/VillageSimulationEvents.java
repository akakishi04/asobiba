package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.Container;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.neoforged.neoforge.event.entity.living.BabyEntitySpawnEvent;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.BaseFireBlock;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.common.BasicItemListing;
import net.neoforged.neoforge.event.entity.player.TradeWithVillagerEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.village.VillagerTradesEvent;

public final class VillageSimulationEvents {
    private static final String BUILD_X = "asobibatweaks_build_x";
    private static final String BUILD_Y = "asobibatweaks_build_y";
    private static final String BUILD_Z = "asobibatweaks_build_z";
    private static final String BUILD_STEP = "asobibatweaks_build_step";
    private static final String BUILD_ACTIVE = "asobibatweaks_build_active";
    private static final String BUILDER_XP = "asobibatweaks_builder_xp";
    private static final String NEXT_BUILD = "asobibatweaks_next_build";
    private static final String DISTRESS = "asobibatweaks_village_distress";
    private static final String BUILD_ANCHOR_X = "asobibatweaks_build_anchor_x";
    private static final String BUILD_ANCHOR_Z = "asobibatweaks_build_anchor_z";
    private static final String BUILD_OUTPOST = "asobibatweaks_build_outpost";
    private static final String SETTLE_X = "asobibatweaks_settle_x";
    private static final String SETTLE_Y = "asobibatweaks_settle_y";
    private static final String SETTLE_Z = "asobibatweaks_settle_z";
    private static final String SETTLE_UNTIL = "asobibatweaks_settle_until";

    @SubscribeEvent
    public void onTrades(VillagerTradesEvent event) {
        if (event.getType() != AsobibaRegistries.CARPENTER.value()) return;

        event.getTrades().get(1).add(new BasicItemListing(
                new ItemStack(Items.OAK_LOG, 16), new ItemStack(Items.EMERALD), 16, 2, 0.05F));
        event.getTrades().get(1).add(new BasicItemListing(
                1, new ItemStack(Items.SCAFFOLDING, 8), 12, 1));
        event.getTrades().get(2).add(new BasicItemListing(
                new ItemStack(Items.COBBLESTONE, 24), new ItemStack(Items.EMERALD), 12, 5, 0.05F));
        event.getTrades().get(2).add(new BasicItemListing(
                2, new ItemStack(Items.OAK_DOOR, 4), 12, 5));
        event.getTrades().get(3).add(new BasicItemListing(
                2, new ItemStack(Items.OAK_FENCE, 12), 12, 10));
        event.getTrades().get(4).add(new BasicItemListing(
                3, new ItemStack(Items.BRICKS, 16), 8, 15));
        event.getTrades().get(5).add(new BasicItemListing(
                5, new ItemStack(Items.LANTERN, 4), 6, 25));
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.isBaby()
                || villager.tickCount % 40 != Math.floorMod(villager.getId(), 40)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        respondToFire(villager, level);
        tickSettlementTravel(villager, level);
        tickRefugeeMigration(villager, level);

        VillagerProfession profession = villager.getVillagerData().getProfession();
        if (profession == AsobibaRegistries.CARPENTER.value()) {
            tickCarpenter(villager, level);
        } else if (profession == VillagerProfession.MASON) {
            tickQuarryWorker(villager, level);
        } else if (profession == VillagerProfession.FLETCHER) {
            tickForester(villager, level);
        } else if (profession == VillagerProfession.NONE || profession == VillagerProfession.NITWIT) {
            if ((villager.getUUID().hashCode() & 3) == 0) tickQuartermaster(villager, level);
            else tickPorter(villager, level);
        } else if (profession == VillagerProfession.FARMER) {
            exportVillagerFood(villager, level);
        }

        useBuildingsInRain(villager, level);
    }

    @SubscribeEvent
    public void onBaby(BabyEntitySpawnEvent event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getParentA() instanceof Villager parent)
                || !(event.getParentB() instanceof Villager)) {
            return;
        }

        ServerLevel level = (ServerLevel)parent.level();
        AABB area = parent.getBoundingBox().inflate(28.0D);
        int villagers = level.getEntitiesOfClass(Villager.class, area).size();
        int beds = countBlocks(level, parent.blockPosition(), 24, state -> state.is(BlockTags.BEDS));
        int food = countStorageItems(level, parent.blockPosition(), 18,
                Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT);

        boolean distressed = level.getGameTime() < parent.getPersistentData().getLong(DISTRESS);
        int infrastructureCap = Math.max(2, beds + Math.max(0, food / 24));
        if (distressed || food < 12 || villagers >= infrastructureCap) {
            event.setCanceled(true);
        }
    }

    @SubscribeEvent
    public void onRegionalTrade(TradeWithVillagerEvent event) {
        if (!AsobibaTweaksConfig.REGIONAL_TRADE_VALUE_ENABLED.getAsBoolean()) return;

        if (!(event.getEntity() instanceof ServerPlayer player)) return;
        Villager villager = event.getAbstractVillager() instanceof Villager v ? v : null;
        if (villager == null) return;

        ItemStack paid = event.getMerchantOffer().getCostA();
        Item bonus = regionalBonus(paid.getItem(), villager);
        if (bonus != null && player.getRandom().nextDouble() < 0.55D) {
            ItemStack stack = new ItemStack(bonus);
            if (!player.getInventory().add(stack)) player.drop(stack, false);
            player.displayClientMessage(Component.literal("Remote-region trade bonus")
                    .withStyle(ChatFormatting.GOLD), true);
        }
    }

    private static void tickCarpenter(Villager villager, ServerLevel level) {
        long now = level.getGameTime();
        if (villager.getPersistentData().getBoolean(BUILD_ACTIVE)) {
            buildOneStep(villager, level);
            return;
        }

        if (now < villager.getPersistentData().getLong(NEXT_BUILD)) return;
        if (!isWorkTime(level)) return;

        AABB villageArea = villager.getBoundingBox().inflate(28.0D);
        int population = level.getEntitiesOfClass(Villager.class, villageArea).size();
        int beds = countBlocks(level, villager.blockPosition(), 24, state -> state.is(BlockTags.BEDS));
        if (population < 4 || beds > population + 1) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 12000L);
            return;
        }

        if (countStorageItems(level, villager.blockPosition(), 18, Items.OAK_PLANKS, Items.SPRUCE_PLANKS,
                Items.BIRCH_PLANKS, Items.ACACIA_PLANKS, Items.COBBLESTONE) < 28) {
            requestMaterials(villager, "planks/cobblestone");
            villager.getPersistentData().putLong(NEXT_BUILD, now + 2400L);
            return;
        }

        int builderXp = villager.getPersistentData().getInt(BUILDER_XP);
        boolean outpost = builderXp > 0 && builderXp % 4 == 3;
        BlockPos site = findBuildSite(villager, level, outpost);
        if (site == null) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 12000L);
            return;
        }

        var data = villager.getPersistentData();
        data.putInt(BUILD_X, site.getX());
        data.putInt(BUILD_Y, site.getY());
        data.putInt(BUILD_Z, site.getZ());
        data.putInt(BUILD_STEP, 0);
        data.putBoolean(BUILD_ACTIVE, true);
        data.putBoolean(BUILD_OUTPOST, outpost);
        data.putInt(BUILD_ANCHOR_X, villager.blockPosition().getX());
        data.putInt(BUILD_ANCHOR_Z, villager.blockPosition().getZ());
        villager.getNavigation().moveTo(site.getX() + 2.0D, site.getY(), site.getZ() + 2.0D, 0.7D);
    }

    private static void buildOneStep(Villager villager, ServerLevel level) {
        if (!isWorkTime(level)) return;

        var data = villager.getPersistentData();
        BlockPos base = new BlockPos(data.getInt(BUILD_X), data.getInt(BUILD_Y), data.getInt(BUILD_Z));
        List<BuildStep> plan = hutPlan(level, base, villager);
        int stepIndex = data.getInt(BUILD_STEP);
        if (stepIndex >= plan.size()) {
            data.putBoolean(BUILD_ACTIVE, false);
            data.putLong(NEXT_BUILD, level.getGameTime() + 5L * 24000L);
            data.putInt(BUILDER_XP, data.getInt(BUILDER_XP) + 1);
            BlockPos anchor = new BlockPos(data.getInt(BUILD_ANCHOR_X), base.getY(), data.getInt(BUILD_ANCHOR_Z));
            buildRoadAndBridge(level, villager, base.offset(2, 0, -1), anchor);
            if (data.getBoolean(BUILD_OUTPOST)) {
                sendSettlers(level, villager, base.offset(2, 1, 2));
            }
            data.remove(BUILD_OUTPOST);
            return;
        }

        BuildStep step = plan.get(stepIndex);
        if (villager.distanceToSqr(step.pos.getCenter()) > 7.0D * 7.0D) {
            villager.getNavigation().moveTo(step.pos.getX() + 0.5D, step.pos.getY(), step.pos.getZ() + 0.5D, 0.75D);
            return;
        }

        if (!level.getBlockState(step.pos).canBeReplaced() && !level.getBlockState(step.pos).is(step.state.getBlock())) {
            data.putBoolean(BUILD_ACTIVE, false);
            data.putLong(NEXT_BUILD, level.getGameTime() + 12000L);
            return;
        }

        if (step.cost != null && !takeFromStorage(level, villager.blockPosition(), 18, step.cost, 1)) {
            requestMaterials(villager, step.cost.getDescription().getString().toLowerCase(Locale.ROOT));
            return;
        }

        level.setBlock(step.pos, step.state, Block.UPDATE_ALL);
        data.putInt(BUILD_STEP, stepIndex + 1);
    }

    private static List<BuildStep> hutPlan(ServerLevel level, BlockPos base, Villager villager) {
        List<BuildStep> steps = new ArrayList<>();
        Block plankBlock = choosePlanks(level, base);
        Item plankItem = plankBlock.asItem();
        BlockState plank = plankBlock.defaultBlockState();
        BlockState cobble = Blocks.COBBLESTONE.defaultBlockState();

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            steps.add(new BuildStep(base.offset(x, 0, z), cobble, Items.COBBLESTONE));
        }

        for (int y = 1; y <= 3; y++) {
            for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                boolean edge = x == 0 || x == 4 || z == 0 || z == 4;
                boolean doorway = z == 0 && x == 2 && y <= 2;
                boolean window = y == 2 && ((x == 0 || x == 4) && z == 2);
                if (edge && !doorway && !window) {
                    BlockState state = plank;
                    if (villager.getPersistentData().getInt(BUILDER_XP) < 2
                            && Math.floorMod((x * 31 + y * 17 + z * 13 + base.hashCode()), 37) == 0) {
                        state = cobble;
                    }
                    steps.add(new BuildStep(base.offset(x, y, z), state,
                            state.is(Blocks.COBBLESTONE) ? Items.COBBLESTONE : plankItem));
                }
            }
        }

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            steps.add(new BuildStep(base.offset(x, 4, z), plank, plankItem));
        }

        BlockState bedFoot = Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT)
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        BlockState bedHead = bedFoot.setValue(BedBlock.PART, BedPart.HEAD);
        steps.add(new BuildStep(base.offset(2, 1, 2), bedFoot, Items.WHITE_BED));
        steps.add(new BuildStep(base.offset(2, 1, 3), bedHead, null));
        steps.add(new BuildStep(base.offset(2, 2, 3), Blocks.TORCH.defaultBlockState(), Items.TORCH));
        if (villager.getPersistentData().getBoolean(BUILD_OUTPOST)) {
            steps.add(new BuildStep(base.offset(1, 1, 2), Blocks.BELL.defaultBlockState(), Items.BELL));
            steps.add(new BuildStep(base.offset(3, 1, 2), Blocks.BARREL.defaultBlockState(), Items.BARREL));
        }
        return steps;
    }

    private static Block choosePlanks(ServerLevel level, BlockPos pos) {
        String biome = level.getBiome(pos).unwrapKey().map(k -> k.location().getPath()).orElse("");
        if (biome.contains("taiga") || biome.contains("snow")) return Blocks.SPRUCE_PLANKS;
        if (biome.contains("birch")) return Blocks.BIRCH_PLANKS;
        if (biome.contains("savanna")) return Blocks.ACACIA_PLANKS;
        if (biome.contains("jungle")) return Blocks.JUNGLE_PLANKS;
        if (biome.contains("mangrove")) return Blocks.MANGROVE_PLANKS;
        if (biome.contains("cherry")) return Blocks.CHERRY_PLANKS;
        return Blocks.OAK_PLANKS;
    }

    private static BlockPos findBuildSite(Villager villager, ServerLevel level, boolean outpost) {
        long salt = villager.getUUID().getLeastSignificantBits() ^ level.getGameTime() / 24000L;
        for (int attempt = 0; attempt < 12; attempt++) {
            double angle = ((salt + attempt * 0x9E3779B97F4A7C15L) >>> 11) * 0x1.0p-53 * Math.PI * 2.0D;
            int radius = outpost
                    ? 30 + Math.floorMod(Long.hashCode(salt + attempt), 18)
                    : 10 + Math.floorMod(Long.hashCode(salt + attempt), 9);
            int x = (int)Math.floor(villager.getX() + Math.cos(angle) * radius);
            int z = (int)Math.floor(villager.getZ() + Math.sin(angle) * radius);
            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos base = new BlockPos(x - 2, y, z - 2);

            boolean clear = true;
            for (int dx = 0; dx < 5 && clear; dx++) for (int dz = 0; dz < 5 && clear; dz++) {
                BlockPos floor = base.offset(dx, -1, dz);
                if (level.getBlockState(floor).isAir() || !level.getFluidState(floor).isEmpty()) clear = false;
                for (int dy = 0; dy <= 4; dy++) {
                    BlockState state = level.getBlockState(base.offset(dx, dy, dz));
                    if (!state.canBeReplaced() && !state.is(BlockTags.REPLACEABLE_BY_TREES)) {
                        clear = false;
                        break;
                    }
                }
            }
            if (clear) return base;
        }
        return null;
    }

    private static void buildRoadAndBridge(ServerLevel level, Villager villager, BlockPos from, BlockPos to) {
        int dx = to.getX() - from.getX();
        int dz = to.getZ() - from.getZ();
        int steps = Math.min(56, Math.max(Math.abs(dx), Math.abs(dz)));
        if (steps <= 0) return;

        for (int i = 0; i <= steps; i++) {
            double t = i / (double)steps;
            int x = (int)Math.round(from.getX() + dx * t);
            int z = (int)Math.round(from.getZ() + dz * t);
            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos surface = new BlockPos(x, y - 1, z);
            if (level.getFluidState(surface).is(FluidTags.WATER)) {
                if (takeAnyPlank(level, villager.blockPosition(), 22)) {
                    level.setBlock(surface, choosePlanks(level, surface).defaultBlockState(), Block.UPDATE_ALL);
                }
            } else {
                BlockState state = level.getBlockState(surface);
                if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT) || state.is(Blocks.COARSE_DIRT)) {
                    level.setBlock(surface, Blocks.DIRT_PATH.defaultBlockState(), Block.UPDATE_ALL);
                }
            }
        }
    }

    private static boolean takeAnyPlank(ServerLevel level, BlockPos center, int radius) {
        return takeFromStorage(level, center, radius, Items.OAK_PLANKS, 1)
                || takeFromStorage(level, center, radius, Items.SPRUCE_PLANKS, 1)
                || takeFromStorage(level, center, radius, Items.BIRCH_PLANKS, 1)
                || takeFromStorage(level, center, radius, Items.ACACIA_PLANKS, 1)
                || takeFromStorage(level, center, radius, Items.JUNGLE_PLANKS, 1)
                || takeFromStorage(level, center, radius, Items.MANGROVE_PLANKS, 1)
                || takeFromStorage(level, center, radius, Items.CHERRY_PLANKS, 1);
    }

    private static void sendSettlers(ServerLevel level, Villager carpenter, BlockPos target) {
        long until = level.getGameTime() + 3L * 24000L;
        List<Villager> candidates = level.getEntitiesOfClass(
                Villager.class,
                carpenter.getBoundingBox().inflate(28.0D),
                v -> v != carpenter && !v.isBaby()
        );
        int sent = 0;
        for (Villager settler : candidates) {
            VillagerProfession profession = settler.getVillagerData().getProfession();
            if (profession != VillagerProfession.NONE && profession != VillagerProfession.NITWIT
                    && profession != VillagerProfession.FARMER) continue;
            var data = settler.getPersistentData();
            data.putInt(SETTLE_X, target.getX());
            data.putInt(SETTLE_Y, target.getY());
            data.putInt(SETTLE_Z, target.getZ());
            data.putLong(SETTLE_UNTIL, until);
            settler.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.75D);
            if (++sent >= 2) break;
        }
    }

    private static void tickSettlementTravel(Villager villager, ServerLevel level) {
        long until = villager.getPersistentData().getLong(SETTLE_UNTIL);
        if (until <= 0L) return;
        if (level.getGameTime() > until) {
            villager.getPersistentData().remove(SETTLE_UNTIL);
            return;
        }

        BlockPos target = new BlockPos(
                villager.getPersistentData().getInt(SETTLE_X),
                villager.getPersistentData().getInt(SETTLE_Y),
                villager.getPersistentData().getInt(SETTLE_Z)
        );
        if (villager.distanceToSqr(target.getCenter()) < 16.0D) {
            villager.getPersistentData().remove(SETTLE_UNTIL);
            return;
        }
        villager.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.78D);
    }

    private static void tickRefugeeMigration(Villager villager, ServerLevel level) {
        if (level.getGameTime() >= villager.getPersistentData().getLong(DISTRESS)
                || villager.getPersistentData().getLong(SETTLE_UNTIL) > 0L
                || villager.tickCount % 400 != Math.floorMod(villager.getId(), 400)) {
            return;
        }

        int beds = countBlocks(level, villager.blockPosition(), 18, state -> state.is(BlockTags.BEDS));
        int food = countStorageItems(level, villager.blockPosition(), 14, Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT);
        if (beds > 0 && food >= 8) return;

        List<Villager> possible = level.getEntitiesOfClass(
                Villager.class,
                villager.getBoundingBox().inflate(112.0D),
                other -> other != villager
                        && other.distanceToSqr(villager) > 48.0D * 48.0D
                        && countBlocks(level, other.blockPosition(), 12, state -> state.is(BlockTags.BEDS)) > 0
        );
        if (possible.isEmpty()) return;

        Villager targetVillager = possible.getFirst();
        BlockPos target = targetVillager.blockPosition();
        var data = villager.getPersistentData();
        data.putInt(SETTLE_X, target.getX());
        data.putInt(SETTLE_Y, target.getY());
        data.putInt(SETTLE_Z, target.getZ());
        data.putLong(SETTLE_UNTIL, level.getGameTime() + 2L * 24000L);
        villager.getNavigation().moveTo(targetVillager, 0.85D);
    }

    private static void tickQuartermaster(Villager villager, ServerLevel level) {
        if (level.getGameTime() % 240 != Math.floorMod(villager.getId(), 240)) return;
        List<Container> stores = containers(level, villager.blockPosition(), 14);
        for (Container store : stores) {
            for (int i = 0; i < store.getContainerSize(); i++) {
                ItemStack a = store.getItem(i);
                if (a.isEmpty()) continue;
                for (int j = i + 1; j < store.getContainerSize(); j++) {
                    ItemStack b = store.getItem(j);
                    if (!ItemStack.isSameItemSameComponents(a, b) || b.isEmpty()) continue;
                    int move = Math.min(b.getCount(), a.getMaxStackSize() - a.getCount());
                    if (move <= 0) continue;
                    a.grow(move);
                    b.shrink(move);
                    store.setChanged();
                }
            }
        }

        int food = countStorageItems(level, villager.blockPosition(), 14, Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT);
        if (food < 16) requestMaterials(villager, "food reserves");
    }

    private static void tickQuarryWorker(Villager villager, ServerLevel level) {
        if (!isWorkTime(level) || level.getGameTime() % 200 != Math.floorMod(villager.getId(), 200)) return;

        BlockPos center = villager.blockPosition();
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-8, -3, -8), center.offset(8, 3, 8))) {
            BlockState state = level.getBlockState(pos);
            if (!state.is(Blocks.STONE) && !state.is(Blocks.ANDESITE) && !state.is(Blocks.DIORITE) && !state.is(Blocks.GRANITE)) continue;
            if (!hasExposedFace(level, pos) || nearProtectedBuildingBlock(level, pos)) continue;
            if (!insertIntoStorage(level, center, 14, new ItemStack(Items.COBBLESTONE))) return;

            level.setBlock(pos, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
            villager.getNavigation().moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, 0.65D);
            return;
        }
    }

    private static void tickForester(Villager villager, ServerLevel level) {
        if (!isWorkTime(level) || level.getGameTime() % 240 != Math.floorMod(villager.getId(), 240)) return;

        BlockPos center = villager.blockPosition();
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-10, -2, -10), center.offset(10, 5, 10))) {
            BlockState state = level.getBlockState(pos);
            if (!state.is(BlockTags.LOGS) || !treeLooksNatural(level, pos)) continue;

            ItemStack log = new ItemStack(state.getBlock().asItem());
            if (log.isEmpty() || !insertIntoStorage(level, center, 14, log)) return;
            level.setBlock(pos, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);

            if (level.getBlockState(pos.below()).is(BlockTags.DIRT)
                    && level.getBlockState(pos).isAir()) {
                Block sapling = saplingFor(state.getBlock());
                if (sapling != null) level.setBlock(pos, sapling.defaultBlockState(), Block.UPDATE_ALL);
            }
            villager.getNavigation().moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, 0.7D);
            return;
        }
    }

    private static void tickPorter(Villager villager, ServerLevel level) {
        if (level.getGameTime() % 100 != Math.floorMod(villager.getId(), 100)) return;
        List<ItemEntity> drops = level.getEntitiesOfClass(
                ItemEntity.class,
                villager.getBoundingBox().inflate(7.0D),
                item -> item.isAlive() && !item.getItem().isEmpty()
        );
        if (drops.isEmpty()) return;

        ItemEntity nearest = drops.getFirst();
        if (villager.distanceToSqr(nearest) > 2.25D) {
            villager.getNavigation().moveTo(nearest, 0.7D);
            return;
        }

        ItemStack copy = nearest.getItem().copy();
        if (insertIntoStorage(level, villager.blockPosition(), 14, copy)) {
            nearest.discard();
        }
    }

    private static void exportVillagerFood(Villager villager, ServerLevel level) {
        if (level.getGameTime() % 300 != Math.floorMod(villager.getId(), 300)) return;
        for (int i = 0; i < villager.getInventory().getContainerSize(); i++) {
            ItemStack stack = villager.getInventory().getItem(i);
            if (!(stack.is(Items.BREAD) || stack.is(Items.CARROT) || stack.is(Items.POTATO) || stack.is(Items.BEETROOT))
                    || stack.getCount() < 8) continue;
            ItemStack exported = stack.copyWithCount(Math.min(4, stack.getCount() - 4));
            if (insertIntoStorage(level, villager.blockPosition(), 12, exported)) {
                stack.shrink(exported.getCount());
            }
            return;
        }
    }

    private static void respondToFire(Villager villager, ServerLevel level) {
        BlockPos center = villager.blockPosition();
        BlockPos fire = null;
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-7, -3, -7), center.offset(7, 4, 7))) {
            if (level.getBlockState(pos).getBlock() instanceof BaseFireBlock) {
                fire = pos.immutable();
                break;
            }
        }
        if (fire == null) return;

        villager.getPersistentData().putLong(DISTRESS, level.getGameTime() + 2L * 24000L);
        if (nearWater(level, fire, 7)) {
            if (villager.distanceToSqr(fire.getCenter()) <= 16.0D) {
                level.setBlock(fire, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
            } else {
                villager.getNavigation().moveTo(fire.getX(), fire.getY(), fire.getZ(), 0.9D);
            }
        } else {
            Vec3Away.moveAway(villager, fire);
        }
    }

    private static void useBuildingsInRain(Villager villager, ServerLevel level) {
        if (!level.isRainingAt(villager.blockPosition()) || villager.getNavigation().isInProgress()) return;

        BlockPos center = villager.blockPosition();
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-8, -1, -8), center.offset(8, 2, 8))) {
            if (!level.getBlockState(pos).isAir()) continue;
            if (!level.getBlockState(pos.above(2)).isAir() && level.getBlockState(pos.below()).isFaceSturdy(level, pos.below(), Direction.UP)) {
                villager.getNavigation().moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, 0.65D);
                return;
            }
        }
    }

    private static boolean takeFromStorage(ServerLevel level, BlockPos center, int radius, Item item, int count) {
        int remaining = count;
        for (Container container : containers(level, center, radius)) {
            for (int i = 0; i < container.getContainerSize(); i++) {
                ItemStack stack = container.getItem(i);
                if (!stack.is(item)) continue;
                int take = Math.min(remaining, stack.getCount());
                stack.shrink(take);
                container.setChanged();
                remaining -= take;
                if (remaining <= 0) return true;
            }
        }
        return false;
    }

    private static boolean insertIntoStorage(ServerLevel level, BlockPos center, int radius, ItemStack incoming) {
        if (incoming.isEmpty()) return true;
        ItemStack work = incoming.copy();

        for (Container container : containers(level, center, radius)) {
            for (int i = 0; i < container.getContainerSize(); i++) {
                ItemStack stack = container.getItem(i);
                if (!stack.isEmpty() && ItemStack.isSameItemSameComponents(stack, work)
                        && stack.getCount() < stack.getMaxStackSize()) {
                    int move = Math.min(work.getCount(), stack.getMaxStackSize() - stack.getCount());
                    stack.grow(move);
                    work.shrink(move);
                    container.setChanged();
                    if (work.isEmpty()) return true;
                }
            }
            for (int i = 0; i < container.getContainerSize(); i++) {
                if (container.getItem(i).isEmpty()) {
                    container.setItem(i, work.copy());
                    container.setChanged();
                    return true;
                }
            }
        }
        return false;
    }

    private static List<Container> containers(ServerLevel level, BlockPos center, int radius) {
        List<Container> result = new ArrayList<>();
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-radius, -3, -radius), center.offset(radius, 3, radius))) {
            if (level.getBlockEntity(pos) instanceof Container container) result.add(container);
        }
        return result;
    }

    private static int countStorageItems(ServerLevel level, BlockPos center, int radius, Item... items) {
        int count = 0;
        outer:
        for (Container container : containers(level, center, radius)) {
            for (int i = 0; i < container.getContainerSize(); i++) {
                ItemStack stack = container.getItem(i);
                for (Item item : items) {
                    if (stack.is(item)) {
                        count += stack.getCount();
                        continue outer;
                    }
                }
            }
        }
        return count;
    }

    private static int countBlocks(ServerLevel level, BlockPos center, int radius, java.util.function.Predicate<BlockState> predicate) {
        int count = 0;
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-radius, -5, -radius), center.offset(radius, 5, radius))) {
            if (predicate.test(level.getBlockState(pos)) && ++count >= 64) break;
        }
        return count;
    }

    private static boolean hasExposedFace(ServerLevel level, BlockPos pos) {
        for (Direction direction : Direction.values()) {
            if (level.getBlockState(pos.relative(direction)).isAir()) return true;
        }
        return false;
    }

    private static boolean nearProtectedBuildingBlock(ServerLevel level, BlockPos pos) {
        for (BlockPos p : BlockPos.betweenClosed(pos.offset(-3, -2, -3), pos.offset(3, 3, 3))) {
            BlockState state = level.getBlockState(p);
            if (state.is(BlockTags.BEDS) || state.is(Blocks.CHEST) || state.is(Blocks.BARREL)
                    || state.is(AsobibaRegistries.CARPENTER_WORKBENCH.get())) return true;
        }
        return false;
    }

    private static boolean treeLooksNatural(ServerLevel level, BlockPos pos) {
        boolean leaves = false;
        for (BlockPos p : BlockPos.betweenClosed(pos.offset(-3, 0, -3), pos.offset(3, 5, 3))) {
            if (level.getBlockState(p).is(BlockTags.LEAVES)) {
                leaves = true;
                break;
            }
        }
        return leaves && !nearProtectedBuildingBlock(level, pos);
    }

    private static Block saplingFor(Block log) {
        if (log == Blocks.SPRUCE_LOG) return Blocks.SPRUCE_SAPLING;
        if (log == Blocks.BIRCH_LOG) return Blocks.BIRCH_SAPLING;
        if (log == Blocks.JUNGLE_LOG) return Blocks.JUNGLE_SAPLING;
        if (log == Blocks.ACACIA_LOG) return Blocks.ACACIA_SAPLING;
        if (log == Blocks.DARK_OAK_LOG) return Blocks.DARK_OAK_SAPLING;
        if (log == Blocks.MANGROVE_LOG) return Blocks.MANGROVE_PROPAGULE;
        if (log == Blocks.CHERRY_LOG) return Blocks.CHERRY_SAPLING;
        if (log == Blocks.OAK_LOG) return Blocks.OAK_SAPLING;
        return null;
    }

    private static boolean nearWater(ServerLevel level, BlockPos center, int radius) {
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-radius, -2, -radius), center.offset(radius, 2, radius))) {
            if (level.getFluidState(pos).is(FluidTags.WATER)) return true;
        }
        return false;
    }

    private static boolean isWorkTime(ServerLevel level) {
        long t = Math.floorMod(level.getDayTime(), 24000L);
        return t >= 1500L && t <= 10500L && !level.isThundering();
    }

    private static void requestMaterials(Villager villager, String what) {
        long now = villager.level().getGameTime();
        long last = villager.getPersistentData().getLong("asobibatweaks_last_request");
        if (now - last < 1200L) return;
        villager.getPersistentData().putLong("asobibatweaks_last_request", now);

        var nearest = ((ServerLevel)villager.level()).getNearestPlayer(villager, 20.0D);
        if (nearest instanceof ServerPlayer player) {
            player.sendSystemMessage(net.minecraft.network.chat.Component.literal(
                    "Village carpenter needs " + what + " for current work."
            ).withStyle(ChatFormatting.YELLOW));
        }
    }

    private static Item regionalBonus(Item item, Villager villager) {
        String biome = villager.level().getBiome(villager.blockPosition())
                .unwrapKey().map(k -> k.location().getPath()).orElse("");

        boolean cold = biome.contains("snow") || biome.contains("frozen") || biome.contains("taiga");
        boolean dry = biome.contains("desert") || biome.contains("badlands") || biome.contains("savanna");

        if (cold && (item == Items.CACTUS || item == Items.SAND || item == Items.TERRACOTTA)) return Items.EMERALD;
        if (dry && (item == Items.SNOW_BLOCK || item == Items.ICE || item == Items.SPRUCE_LOG)) return Items.EMERALD;
        if (!cold && !dry && (item == Items.PACKED_ICE || item == Items.RED_SAND)) return Items.EMERALD;
        return null;
    }

    private record BuildStep(BlockPos pos, BlockState state, Item cost) {}

    private static final class Vec3Away {
        static void moveAway(Villager villager, BlockPos danger) {
            double dx = villager.getX() - danger.getX();
            double dz = villager.getZ() - danger.getZ();
            double len = Math.max(0.001D, Math.sqrt(dx * dx + dz * dz));
            villager.getNavigation().moveTo(
                    villager.getX() + dx / len * 10.0D,
                    villager.getY(),
                    villager.getZ() + dz / len * 10.0D,
                    1.0D
            );
        }
    }
}
