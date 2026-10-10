package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.animal.Chicken;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.ai.village.poi.PoiTypes;
import net.minecraft.world.entity.schedule.Activity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.BellBlock;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CampfireBlock;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Real loaded worlds, mobs, enchantment components, block states and production event transactions. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class AmbientSocialGameTests {
    private static final BlockPos PLAYER = new BlockPos(3, 2, 8);
    private AmbientSocialGameTests() {}

    @GameTest(template = "empty16x14x16", batch = "ambient_blocks")
    public static void naturalKnockAndSmokeDoNotEditBlocksOrCreateEntities(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, PLAYER);
        var level = helper.getLevel();
        BlockPos fire = helper.absolutePos(new BlockPos(6, 2, 8));
        var cold = Blocks.CAMPFIRE.defaultBlockState().setValue(CampfireBlock.LIT, false);
        level.setBlock(fire, cold, 2);
        int before = AmbientOddityService.nearby(level, net.minecraft.world.entity.Entity.class,
                player.getBoundingBox().inflate(12)).size();
        helper.assertTrue(AmbientOddityService.attempt(player, AmbientOddityService.Kind.EMBER, fire, 0),
                "Unenchanted player must naturally qualify for the real smoke emission");
        helper.assertTrue(level.getBlockState(fire).equals(cold), "Smoke must not light or alter the campfire");
        helper.assertTrue(AmbientOddityService.nearby(level, net.minecraft.world.entity.Entity.class,
                player.getBoundingBox().inflate(12)).size() == before, "Smoke must not create actors or rewards");
        AmbientOddityService.clear(level);
        BlockPos door = fire.offset(0, 0, 2);
        var closed = Blocks.OAK_DOOR.defaultBlockState();
        level.setBlock(door, closed, 2);
        level.setBlock(door.above(), closed.setValue(DoorBlock.HALF, DoubleBlockHalf.UPPER), 2);
        helper.assertTrue(AmbientOddityService.attempt(player, AmbientOddityService.Kind.KNOCK, door, 0),
                "Unenchanted player must naturally qualify for real knock sounds");
        helper.assertTrue(AmbientOddityService.state(level).sounds.size() == 2,
                "Knock must queue exactly two faint native sounds");
        helper.assertTrue(level.getBlockState(door).equals(closed), "Knock must not open or power the door");
        helper.assertTrue(player.getActiveEffects().isEmpty(), "Ambient events must never apply statuses");
        AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_context", skyAccess = true)
    public static void naturalOutdoorBreezeDoesNotChangeVelocity(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, PLAYER);
        var level = helper.getLevel();
        player.setYRot(0);
        Vec3 before = new Vec3(0.025D, 0, -0.02D);
        player.setDeltaMovement(before);
        helper.assertTrue(level.canSeeSky(player.blockPosition()), "Outdoor fixture must see sky");
        helper.assertTrue(AmbientOddityService.attempt(player, AmbientOddityService.Kind.BREEZE,
                player.blockPosition(), 0), "Unenchanted outdoor moment must allow cosmetic breeze");
        helper.assertTrue(player.getDeltaMovement().equals(before), "Dust swirl must not push the player");
        helper.assertTrue(AmbientOddityService.state(level).sounds.isEmpty(), "Breeze is particle-only");
        AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_cave")
    public static void naturalCaveFootstepsAndChordUseFiniteDelayedSounds(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, PLAYER);
        var level = helper.getLevel();
        player.setYRot(0);
        for (int y = 4; y <= 9; y++) helper.setBlock(PLAYER.above(y), Blocks.STONE);
        long stoneRoof = java.util.stream.IntStream.rangeClosed(3, 10).filter(y ->
                level.getBlockState(player.blockPosition().above(y)).is(net.minecraft.tags.BlockTags.BASE_STONE_OVERWORLD)).count();
        helper.assertTrue(AmbientOddityService.cave(level, player.blockPosition()),
                "GameTest cave needs loaded natural-stone overburden: pos=" + player.blockPosition()
                        + ", sea=" + level.getSeaLevel() + ", stone=" + stoneRoof
                        + ", cachedSky=" + level.canSeeSky(player.blockPosition()));
        helper.assertTrue(AmbientOddityService.attempt(player, AmbientOddityService.Kind.FOOTSTEPS,
                player.blockPosition(), 0), "Unenchanted quiet cave must permit footsteps");
        var sounds = AmbientOddityService.state(level).sounds;
        helper.assertTrue(sounds.size() == 3 && sounds.get(0).due() < sounds.get(1).due()
                && sounds.get(1).due() < sounds.get(2).due(), "Footsteps need three soft delayed sounds");
        helper.assertTrue(sounds.stream().allMatch(sound -> sound.position().z < player.getZ()),
                "Footsteps must be beside/behind, not in front of the facing player");
        AmbientOddityService.clear(level);
        helper.assertTrue(AmbientOddityService.attempt(player, AmbientOddityService.Kind.CHORD,
                player.blockPosition(), 0), "Unenchanted quiet cave must permit the chord");
        helper.assertTrue(AmbientOddityService.state(level).sounds.size() == 3,
                "Chord needs a finite three-note phrase with no instrument entity");
        AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_chickens")
    public static void threeIdleChickensConspireAndApproachEndsTheWholeGroup(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, new BlockPos(1, 2, 8));
        List<Chicken> chickens = List.of(chicken(helper, 8, 7), chicken(helper, 8, 8), chicken(helper, 9, 8));
        var level = helper.getLevel();
        Chicken leader = chickens.getFirst();
        leader.goalSelector.addGoal(8, new net.minecraft.world.entity.ai.goal.RandomLookAroundGoal(leader) {
            @Override public boolean canUse() { return true; }
        });
        leader.goalSelector.tick();
        helper.assertTrue(AmbientOddityService.startAnimals(player, AmbientOddityService.Kind.CHICKEN, 0),
                "Three naturally idle loaded chickens must support the independent conspiracy");
        var looks = AmbientOddityService.state(level).looks;
        helper.assertTrue(looks.size() == 3, "Conspiracy must enlist three real chickens");
        Vec3 direction = looks.get(chickens.getFirst().getUUID()).target().subtract(chickens.getFirst().getEyePosition());
        helper.assertTrue(chickens.stream().allMatch(chicken -> looks.get(chicken.getUUID()).target()
                .subtract(chicken.getEyePosition()).distanceToSqr(direction) < 0.00001D),
                "Conspirators must look in one parallel direction");
        float desired = (float)(Math.atan2(direction.z, direction.x) * 180 / Math.PI) - 90;
        leader.setYHeadRot(desired + 90);
        AmbientOddityService.tick(level);
        helper.assertTrue(Math.abs(net.minecraft.util.Mth.wrapDegrees(desired - leader.getYHeadRot())) < 90,
                "Conspiracy must actually turn the tracked head even with a running random-look goal");
        player.setPos(chickens.getFirst().position().add(1, 0, 0));
        AmbientOddityService.tick(level);
        helper.assertTrue(looks.isEmpty(), "Approaching one member must quietly release the entire group");
        helper.assertTrue(chickens.stream().noneMatch(Chicken::isNoAi), "Conspiracy must never disable normal AI");
        AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_safety")
    public static void glanceNaturalAndBreedingNavigationFeedingTakePriority(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, new BlockPos(1, 2, 8));
        Chicken chicken = chicken(helper, 8, 8);
        var level = helper.getLevel();
        helper.assertTrue(AmbientOddityService.startAnimals(player, AmbientOddityService.Kind.GLANCE, 0),
                "One idle animal must naturally support an unusual glance");
        chicken.setInLoveTime(100);
        AmbientOddityService.tick(level);
        helper.assertTrue(AmbientOddityService.state(level).looks.isEmpty(), "Breeding must immediately own the animal");
        chicken.resetLove();
        player.setItemInHand(net.minecraft.world.InteractionHand.MAIN_HAND, new ItemStack(Items.WHEAT_SEEDS));
        var temptation = new net.minecraft.world.entity.ai.goal.TemptGoal(chicken, 1,
                stack -> stack.is(Items.WHEAT_SEEDS), false);
        chicken.goalSelector.addGoal(1, temptation);
        chicken.goalSelector.tick();
        helper.assertTrue(!AmbientOddityService.idle(chicken), "A running native feeding goal must prevent ambient control");
        chicken.goalSelector.removeAllGoals(goal -> true);
        chicken.getNavigation().stop();
        player.setItemInHand(net.minecraft.world.InteractionHand.MAIN_HAND, ItemStack.EMPTY);
        chicken.setTarget(player);
        helper.assertTrue(!AmbientOddityService.idle(chicken), "Combat response must prevent ambient control");
        chicken.setTarget(null);
        chicken.getNavigation().moveTo(chicken.getX() + 3, chicken.getY(), chicken.getZ(), 0.7D);
        var original = chicken.getNavigation().getPath();
        helper.assertTrue(original != null && !AmbientOddityService.idle(chicken)
                && chicken.getNavigation().getPath() == original, "An existing real path must retain ownership");
        AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_bias")
    public static void ominousIsCappedAndCannotBypassDisabledEventOrCooldown(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, PLAYER);
        var level = helper.getLevel();
        double natural = AmbientOddityService.chance(player, 0.02D);
        enchant(player, EquipmentSlot.CHEST, Items.DIAMOND_CHESTPLATE, NewEnchantments.OMINOUS);
        double one = AmbientOddityService.chance(player, 0.02D);
        enchant(player, EquipmentSlot.HEAD, Items.DIAMOND_HELMET, NewEnchantments.OMINOUS);
        enchant(player, EquipmentSlot.LEGS, Items.DIAMOND_LEGGINGS, NewEnchantments.OMINOUS);
        enchant(player, EquipmentSlot.FEET, Items.DIAMOND_BOOTS, NewEnchantments.OMINOUS);
        helper.assertTrue(natural == 0.02D && Math.abs(one - 0.025D) < 0.00001D
                && one == AmbientOddityService.chance(player, 0.02D), "Armor pieces must never multiply the bounded bias");
        BlockPos fire = helper.absolutePos(new BlockPos(6, 2, 8));
        level.setBlock(fire, Blocks.CAMPFIRE.defaultBlockState().setValue(CampfireBlock.LIT, false), 2);
        boolean wasEnabled = AsobibaTweaksConfig.OE_COLD_EMBER_ENABLED.getAsBoolean();
        try {
            AsobibaTweaksConfig.OE_COLD_EMBER_ENABLED.set(false);
            helper.assertTrue(!AmbientOddityService.attempt(player, AmbientOddityService.Kind.EMBER, fire, 0),
                    "Ominous must respect independent disabled event");
        } finally { AsobibaTweaksConfig.OE_COLD_EMBER_ENABLED.set(wasEnabled); }
        helper.assertTrue(AmbientOddityService.attempt(player, AmbientOddityService.Kind.EMBER, fire, 0), "Eligible enabled event must start");
        var second = helper.makeMockServerPlayerInLevel();
        second.setPos(player.position()); second.setOnGround(true);
        enchant(second, EquipmentSlot.CHEST, Items.DIAMOND_CHESTPLATE, NewEnchantments.OMINOUS);
        helper.assertTrue(!AmbientOddityService.attempt(second, AmbientOddityService.Kind.EMBER, fire, 0),
                "Multiple Ominous wearers must share global/local cooldowns");
        AmbientOddityService.clear(level);
        player.discard(); second.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_limits")
    public static void boundsAndUnknownChunksFailClosed(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, PLAYER);
        var level = helper.getLevel();
        BlockPos unknown = player.blockPosition().offset(1000000, 0, 1000000);
        helper.assertTrue(!level.hasChunkAt(unknown), "Unknown-chunk fixture must be unloaded");
        helper.assertTrue(!AmbientOddityService.attempt(player, AmbientOddityService.Kind.EMBER, unknown, 0)
                && !level.hasChunkAt(unknown), "Ambient checks must not force-load chunks");
        for (int i = 0; i < AmbientOddityService.MAX_QUERY_RESULTS + 3; i++) chicken(helper, 8, 8);
        helper.assertTrue(AmbientOddityService.nearby(level, Chicken.class,
                player.getBoundingBox().inflate(12)).size() == AmbientOddityService.MAX_QUERY_RESULTS,
                "Native entity collection must stop at the hard query budget");
        helper.assertTrue(!AmbientOddityService.startAnimals(player, AmbientOddityService.Kind.CHICKEN, 0),
                "Saturated farms must fail closed rather than scan every animal");
        helper.assertTrue(AmbientOddityService.claimProbe(level) && AmbientOddityService.claimProbe(level)
                && !AmbientOddityService.claimProbe(level), "Only two expensive attempts may run per dimension tick");
        AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_bell")
    public static void bellReplyRequiresActualVillageNightBellAndNeverReringsIt(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, PLAYER);
        var level = helper.getLevel();
        BlockPos bell = helper.absolutePos(new BlockPos(6, 2, 8));
        level.setBlock(bell, Blocks.BELL.defaultBlockState(), 2);
        long time = level.getDayTime();
        BlockPos home = bell.north(2);
        var poi = level.registryAccess().lookupOrThrow(Registries.POINT_OF_INTEREST_TYPE).getOrThrow(PoiTypes.HOME);
        level.getPoiManager().add(home, poi);
        level.getPoiManager().take(type -> type.is(PoiTypes.HOME), (type, pos) -> pos.equals(home), home, 1);
        try {
            level.setDayTime(6000);
            helper.assertTrue(!AmbientOddityService.bellRang(level, bell, 0), "Daytime must reject the reply");
            AmbientOddityService.clear(level);
            level.setDayTime(14000);
            helper.assertTrue(level.isVillage(bell), "Occupied native home POI must define the fixture village");
            helper.assertTrue(AmbientOddityService.bellRang(level, bell, 0), "Unenchanted observer must allow a natural night reply");
            var blockEntity = (net.minecraft.world.level.block.entity.BellBlockEntity)level.getBlockEntity(bell);
            helper.assertTrue(blockEntity != null && !blockEntity.shaking,
                    "An ambient reply must not ring the real bell or trigger its alert logic");
            helper.assertTrue(AmbientOddityService.state(level).sounds.size() == 1
                    && AmbientOddityService.state(level).sounds.getFirst().position().distanceToSqr(Vec3.atCenterOf(bell)) >= 36,
                    "Reply must be one faint distant queued native sound");
            AmbientOddityService.clear(level);
            // Exercise the actual vanilla success hook as well; a failed/no-bell interaction cannot invoke it.
            helper.assertTrue(((BellBlock)Blocks.BELL).attemptToRing(player, level, bell, Direction.NORTH),
                    "Fixture must execute the real successful vanilla bell ring");
        } finally {
            level.setDayTime(time);
            level.getPoiManager().remove(home);
            AmbientOddityService.clear(level);
            player.discard();
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "nod_eligibility")
    public static void nodNeedsOwnHelmetFacingCrouchAndIdleAdultOrBaby(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, new BlockPos(5, 2, 8));
        Villager villager = villager(helper, new BlockPos(8, 2, 8));
        var level = helper.getLevel();
        face(player, villager);
        player.setShiftKeyDown(true);
        enchant(player, EquipmentSlot.CHEST, Items.DIAMOND_CHESTPLATE, NewEnchantments.OMINOUS);
        helper.assertTrue(!NodGreetingEvents.attemptGreeting(player, 0), "Ominous alone must never grant Nod");
        enchant(player, EquipmentSlot.HEAD, Items.DIAMOND_HELMET, NewEnchantments.NOD);
        player.setShiftKeyDown(false);
        helper.assertTrue(!NodGreetingEvents.attemptGreeting(player, 0), "Merely wearing Nod must not trigger a gesture");
        player.setShiftKeyDown(true);
        player.setYRot(player.getYRot() + 180);
        helper.assertTrue(!NodGreetingEvents.attemptGreeting(player, 0), "Greeting must face the villager");
        face(player, villager);
        AmbientOddityService.clear(level);
        helper.assertTrue(NodGreetingEvents.attemptGreeting(player, 0), "Safe idle adult must support the genuine eligible gesture");
        helper.assertTrue(NodGreetingEvents.gestures(level).containsKey(villager.getUUID()), "Server must own a bounded animation window");
        helper.assertTrue(!villager.isTrading() && villager.getTarget() == null, "Nod must not start trade or combat");
        NodGreetingEvents.clear(level); AmbientOddityService.clear(level);
        villager.setBaby(true);
        face(player, villager);
        helper.assertTrue(NodGreetingEvents.attemptGreeting(player, 0), "Idle babies must also be eligible");
        villager.getBrain().setActiveActivityIfPossible(Activity.PANIC);
        NodGreetingEvents.tickGesture(villager);
        helper.assertTrue(NodGreetingEvents.gestures(level).isEmpty(), "Panic must cancel the gesture immediately");
        NodGreetingEvents.clear(level); AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "nod_lifecycle")
    public static void nodRequiresCrouchEdgeAndNeverLeaksRemovedVillagers(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, new BlockPos(5, 2, 8));
        Villager villager = villager(helper, new BlockPos(8, 2, 8));
        var level = helper.getLevel();
        enchant(player, EquipmentSlot.HEAD, Items.DIAMOND_HELMET, NewEnchantments.NOD);
        face(player, villager);
        player.setShiftKeyDown(true);
        NodGreetingEvents.tickGreeting(player);
        for (int i = 0; i < 8; i++) NodGreetingEvents.tickGreeting(player);
        helper.assertTrue(NodGreetingEvents.gestures(level).isEmpty(), "Joining or holding crouch is not a new greeting");
        helper.assertTrue(NodGreetingEvents.attemptGreeting(player, 0), "Eligible fixture must install an actual gesture");
        villager.discard();
        NodGreetingEvents.cleanGestures(level);
        helper.assertTrue(NodGreetingEvents.gestures(level).isEmpty(), "Removed non-ticking villagers must release the animation cap");
        helper.assertTrue(NodGreetingEvents.nodPitch(0) == 0 && NodGreetingEvents.nodPitch(12) > 23
                && Math.abs(NodGreetingEvents.nodPitch(24)) < 0.0001D, "The brief head gesture must move down and return");
        NodGreetingEvents.clear(level); AmbientOddityService.clear(level);
        player.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "nod_real_greeting", timeoutTicks = 50)
    public static void elapsedStandingThenCrouchStartsExactlyOneGreeting(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, new BlockPos(5, 2, 8));
        Villager villager = villager(helper, new BlockPos(8, 2, 8));
        villager.getBrain().removeAllBehaviors();
        villager.getBrain().setSchedule(net.minecraft.world.entity.schedule.Schedule.EMPTY);
        var level = helper.getLevel();
        enchant(player, EquipmentSlot.HEAD, Items.DIAMOND_HELMET, NewEnchantments.NOD);
        face(player, villager);
        player.setShiftKeyDown(false);
        NodGreetingEvents.tickGreeting(player);
        double original = AsobibaTweaksConfig.NOD_GREETING_CHANCE.getAsDouble();
        helper.runAtTickTime(10, () -> {
            AmbientOddityService.clear(level);
            AsobibaTweaksConfig.NOD_GREETING_CHANCE.set(1.0D);
            villager.getBrain().eraseMemory(MemoryModuleType.WALK_TARGET);
            villager.getBrain().setActiveActivityIfPossible(Activity.IDLE);
            villager.getNavigation().stop();
            villager.setDeltaMovement(Vec3.ZERO);
            villager.setOnGround(true);
            face(player, villager);
            player.setShiftKeyDown(true);
            NodGreetingEvents.tickGreeting(player);
        });
        helper.runAtTickTime(16, () -> {
            try {
                helper.assertTrue(NodGreetingEvents.gestures(level).containsKey(villager.getUUID()),
                        "Eight real standing ticks then four real crouching ticks must start a server-authorized Nod");
                var started = NodGreetingEvents.gestures(level).get(villager.getUUID());
                for (int i = 0; i < 10; i++) NodGreetingEvents.tickGreeting(player);
                helper.assertTrue(NodGreetingEvents.gestures(level).size() == 1
                        && NodGreetingEvents.gestures(level).get(villager.getUUID()).start() == started.start(),
                        "Holding crouch must not restart or stack gestures");
                helper.succeed();
            } finally {
                AsobibaTweaksConfig.NOD_GREETING_CHANCE.set(original);
                NodGreetingEvents.clear(level); AmbientOddityService.clear(level);
                player.discard(); villager.discard();
            }
        });
    }

    @GameTest(template = "empty16x14x16", batch = "ambient_gathering")
    public static void gatheringUsesOminousBiasAndNeverStopsAReplacementPath(GameTestHelper helper) {
        floor(helper);
        ServerPlayer player = player(helper, new BlockPos(1, 2, 8));
        List<Chicken> flock = List.of(chicken(helper, 8, 7), chicken(helper, 8, 8),
                chicken(helper, 9, 7), chicken(helper, 9, 8));
        Chicken leader = flock.getFirst();
        leader.tickCount = Math.floorMod(leader.getId(), 1200);
        var events = new WorldOddityEvents();
        double original = AsobibaTweaksConfig.MOB_GATHERING_CHANCE.getAsDouble();
        try {
            AsobibaTweaksConfig.MOB_GATHERING_CHANCE.set(0.002D);
            // Real LegacyRandomSource seed5161 begins with0.0024888: outside the ordinary
            // chance, inside the one-piece capped Ominous chance0.0025.
            leader.getRandom().setSeed(5161);
            events.onEntityTick(new net.neoforged.neoforge.event.tick.EntityTickEvent.Post(leader));
            helper.assertTrue(leader.getPersistentData().getLong("asobibatweaks_gather_until") == 0,
                    "Ordinary gathering chance must reject the seeded roll");
            enchant(player, EquipmentSlot.CHEST, Items.DIAMOND_CHESTPLATE, NewEnchantments.OMINOUS);
            leader.getRandom().setSeed(5161);
            events.onEntityTick(new net.neoforged.neoforge.event.tick.EntityTickEvent.Post(leader));
            helper.assertTrue(leader.getPersistentData().getLong("asobibatweaks_gather_until") > helper.getLevel().getGameTime()
                    && leader.getNavigation().getPath() != null, "Ominous should modestly bias the real eligible gathering path");
            var owned = leader.getNavigation().getPath();
            BlockPos replacement = helper.absolutePos(new BlockPos(12, 2, 3));
            helper.assertTrue(leader.getNavigation().moveTo(replacement.getX() + 0.5D,
                    replacement.getY(), replacement.getZ() + 0.5D, 0.8D), "Fixture needs a real replacement AI path");
            var newPath = leader.getNavigation().getPath();
            helper.assertTrue(newPath != owned, "Fixture must replace the gathering-owned path object");
            events.onEntityTick(new net.neoforged.neoforge.event.tick.EntityTickEvent.Post(leader));
            helper.assertTrue(leader.getPersistentData().getLong("asobibatweaks_gather_until") == 0
                    && leader.getNavigation().getPath() == newPath && !leader.getNavigation().isDone(),
                    "Gathering must surrender without stopping a new vanilla/modded navigation path");
        } finally {
            AsobibaTweaksConfig.MOB_GATHERING_CHANCE.set(original);
            AmbientOddityService.clear(helper.getLevel()); player.discard();
        }
        helper.succeed();
    }

    private static ServerPlayer player(GameTestHelper helper, BlockPos pos) {
        AmbientOddityService.clear(helper.getLevel()); NodGreetingEvents.clear(helper.getLevel());
        var player = helper.makeMockServerPlayerInLevel();
        player.setPos(Vec3.atBottomCenterOf(helper.absolutePos(pos)));
        player.setOnGround(true);
        return player;
    }

    private static Chicken chicken(GameTestHelper helper, int x, int z) {
        Chicken chicken = helper.spawn(EntityType.CHICKEN, new BlockPos(x, 2, z));
        chicken.goalSelector.removeAllGoals(goal -> true);
        chicken.setOnGround(true);
        chicken.eggTime = 1000;
        return chicken;
    }

    private static Villager villager(GameTestHelper helper, BlockPos pos) {
        Villager villager = helper.spawn(EntityType.VILLAGER, pos);
        villager.goalSelector.removeAllGoals(goal -> true);
        villager.getBrain().eraseMemory(MemoryModuleType.WALK_TARGET);
        villager.getBrain().setActiveActivityIfPossible(Activity.IDLE);
        villager.setOnGround(true);
        return villager;
    }

    private static void face(ServerPlayer player, Villager villager) {
        Vec3 v = villager.getEyePosition().subtract(player.getEyePosition());
        player.setYRot((float)(Math.atan2(v.z, v.x) * 180 / Math.PI) - 90);
        player.setXRot((float)(-Math.atan2(v.y, v.horizontalDistance()) * 180 / Math.PI));
    }

    private static void enchant(ServerPlayer player, EquipmentSlot slot, net.minecraft.world.item.Item item,
                                net.minecraft.resources.ResourceKey<net.minecraft.world.item.enchantment.Enchantment> key) {
        ItemStack stack = new ItemStack(item);
        stack.enchant(player.registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(key), 1);
        player.setItemSlot(slot, stack);
    }

    private static void floor(GameTestHelper helper) {
        for (BlockPos pos : BlockPos.betweenClosed(new BlockPos(0, 1, 0), new BlockPos(15, 1, 15)))
            helper.setBlock(pos, Blocks.STONE);
    }
}
