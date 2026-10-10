package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import com.mojang.authlib.GameProfile;
import io.netty.channel.embedded.EmbeddedChannel;
import java.util.UUID;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.CommonListenerCookie;
import net.minecraft.network.Connection;
import net.minecraft.network.protocol.PacketFlow;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CropBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.level.BlockEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Exercises real vanilla player harvesting and NeoForge cancellation, not synthetic free planting. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class RootedEnchantmentGameTests {
    private static final BlockPos CROP = new BlockPos(3, 2, 3);
    private RootedEnchantmentGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void fourOrdinaryCropsSpendOneRealSeedAndPreserveHarvestDrops(GameTestHelper h) {
        ServerPlayer player = player(h);
        Block[] crops = {Blocks.WHEAT, Blocks.CARROTS, Blocks.POTATOES, Blocks.BEETROOTS};
        Item[] seeds = {Items.WHEAT_SEEDS, Items.CARROT, Items.POTATO, Items.BEETROOT_SEEDS};
        for (int i = 0; i < crops.length; i++) {
            BlockPos local = CROP.offset(i * 2, 0, 0);
            CropBlock crop = (CropBlock)crops[i];
            plant(h, local, crop.getStateForAge(crop.getMaxAge()));
            plant(h, local.north(), crop.getStateForAge(crop.getMaxAge()));
            player.getInventory().setItem(1, new ItemStack(seeds[i], 3));
            DropProbe probe = new DropProbe(player);
            NeoForge.EVENT_BUS.register(probe);
            try {
                h.assertTrue(player.gameMode.destroyBlock(h.absolutePos(local)), "Real player harvest must succeed");
                h.assertTrue(probe.event != null && !probe.before.isEmpty(), "Actual harvest must emit real vanilla drops");
                RootedEnchantmentEvents.finishHarvests(h.getLevel());
                h.assertTrue(h.getLevel().getBlockState(h.absolutePos(local)).equals(crop.getStateForAge(0)),
                        "Only a young copy of the same ordinary crop may be planted");
                h.assertTrue(player.getInventory().getItem(1).getCount() == 2, "Exactly one owned planting item must be spent");
                h.assertTrue(h.getLevel().getBlockState(h.absolutePos(local.north())).equals(crop.getStateForAge(crop.getMaxAge())),
                        "Adjacent crops must be untouched");
                probe.assertUnchanged(h);
                RootedEnchantmentEvents.finishHarvests(h.getLevel());
                h.assertTrue(player.getInventory().getItem(1).getCount() == 2, "A harvest receipt must not replay");
            } finally {
                NeoForge.EVENT_BUS.unregister(probe);
            }
        }
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void noSeedOrWrongSeedLeavesNormalHarvestAloneAndOffhandSeedIsPaid(GameTestHelper h) {
        ServerPlayer player = player(h);
        for (int i = 0; i < 2; i++) {
            BlockPos local = CROP.offset(i * 2, 0, 0);
            plant(h, local, mature(Blocks.WHEAT));
            player.getInventory().setItem(1, i == 0 ? ItemStack.EMPTY : new ItemStack(Items.BEETROOT_SEEDS, 4));
            h.assertTrue(player.gameMode.destroyBlock(h.absolutePos(local)), "Ordinary harvest must still succeed");
            RootedEnchantmentEvents.finishHarvests(h.getLevel());
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(local)).isAir(), "Missing matching inventory seed must not fabricate a crop");
        }
        h.assertTrue(player.getInventory().getItem(1).getCount() == 4, "Wrong seed must remain owned and intact");
        plant(h, CROP, mature(Blocks.WHEAT));
        player.setItemInHand(InteractionHand.OFF_HAND, new ItemStack(Items.WHEAT_SEEDS, 2));
        player.gameMode.destroyBlock(h.absolutePos(CROP));
        RootedEnchantmentEvents.finishHarvests(h.getLevel());
        h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).is(Blocks.WHEAT)
                && player.getOffhandItem().getCount() == 1, "Offhand seeds are real paid inventory too");
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void immatureCropsAndUnusualPlantsNeverReplant(GameTestHelper h) {
        ServerPlayer player = player(h);
        player.getInventory().setItem(1, new ItemStack(Items.WHEAT_SEEDS, 5));
        plant(h, CROP, ((CropBlock)Blocks.WHEAT).getStateForAge(2));
        player.gameMode.destroyBlock(h.absolutePos(CROP));
        RootedEnchantmentEvents.finishHarvests(h.getLevel());
        h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).isAir()
                && player.getInventory().getItem(1).getCount() == 5, "Immature harvesting must not trigger Rooted");
        h.assertTrue(RootedEnchantmentEvents.seedFor(Blocks.NETHER_WART.defaultBlockState()) == null
                && RootedEnchantmentEvents.seedFor(Blocks.MELON_STEM.defaultBlockState()) == null
                && RootedEnchantmentEvents.seedFor(Blocks.SWEET_BERRY_BUSH.defaultBlockState()) == null
                && RootedEnchantmentEvents.seedFor(Blocks.TORCHFLOWER_CROP.defaultBlockState()) == null,
                "Wart, stems, berries and unusual crops require separate explicit rules");
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void occupiedFluidAndLostFarmlandNeverGetOverwritten(GameTestHelper h) {
        ServerPlayer player = player(h);
        player.getInventory().setItem(1, new ItemStack(Items.WHEAT_SEEDS, 5));
        for (int i = 0; i < 3; i++) {
            BlockPos local = CROP.offset(i * 2, 0, 0);
            plant(h, local, mature(Blocks.WHEAT));
            player.gameMode.destroyBlock(h.absolutePos(local));
            BlockState expected = i == 0 ? Blocks.COBBLESTONE.defaultBlockState()
                    : i == 1 ? Blocks.WATER.defaultBlockState() : Blocks.AIR.defaultBlockState();
            if (i < 2) h.setBlock(local, expected);
            else h.setBlock(local.below(), Blocks.DIRT);
            RootedEnchantmentEvents.finishHarvests(h.getLevel());
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(local)).equals(expected),
                    "Rooted must leave a newly occupied/fluid/unsupported cell alone");
        }
        h.assertTrue(player.getInventory().getItem(1).getCount() == 5, "Failed placement must not charge any seeds");
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void programmaticDestructionAndWrongHeldToolsDoNotCount(GameTestHelper h) {
        ServerPlayer player = player(h);
        player.getInventory().setItem(1, new ItemStack(Items.WHEAT_SEEDS, 5));
        plant(h, CROP, mature(Blocks.WHEAT));
        h.getLevel().destroyBlock(h.absolutePos(CROP), true, player);
        RootedEnchantmentEvents.finishHarvests(h.getLevel());
        h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).isAir(),
                "Player-attributed programmatic destruction is not a player hoe break transaction");
        plant(h, CROP, mature(Blocks.WHEAT));
        player.setItemInHand(InteractionHand.OFF_HAND, player.getMainHandItem().copy());
        player.setItemInHand(InteractionHand.MAIN_HAND, enchanted(h, Items.DIAMOND_PICKAXE));
        player.gameMode.destroyBlock(h.absolutePos(CROP));
        RootedEnchantmentEvents.finishHarvests(h.getLevel());
        h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).isAir()
                && player.getInventory().getItem(1).getCount() == 5, "The actually used main-hand tool must be an enchanted hoe");
        plant(h, CROP, mature(Blocks.WHEAT));
        player.setItemInHand(InteractionHand.MAIN_HAND, new ItemStack(Items.DIAMOND_HOE));
        player.gameMode.destroyBlock(h.absolutePos(CROP));
        RootedEnchantmentEvents.finishHarvests(h.getLevel());
        h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).isAir()
                && player.getInventory().getItem(1).getCount() == 5, "An unenchanted hoe must remain ordinary even beside an enchanted offhand hoe");
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void canceledBreakOrDropsNeverSpendsSeeds(GameTestHelper h) {
        ServerPlayer player = player(h);
        player.getInventory().setItem(1, new ItemStack(Items.WHEAT_SEEDS, 3));
        CancellationProbe probe = new CancellationProbe(player);
        NeoForge.EVENT_BUS.register(probe);
        try {
            plant(h, CROP, mature(Blocks.WHEAT));
            probe.cancelBreak = true;
            h.assertTrue(!player.gameMode.destroyBlock(h.absolutePos(CROP)), "Canceled break must fail");
            RootedEnchantmentEvents.finishHarvests(h.getLevel());
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).equals(mature(Blocks.WHEAT)),
                    "Canceled harvesting must preserve the mature original");
            probe.cancelBreak = false;
            probe.cancelDrops = true;
            player.gameMode.destroyBlock(h.absolutePos(CROP));
            RootedEnchantmentEvents.finishHarvests(h.getLevel());
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).isAir()
                    && player.getInventory().getItem(1).getCount() == 3, "Canceled drop transaction must not plant or spend seeds");
        } finally {
            NeoForge.EVENT_BUS.unregister(probe);
        }
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void canceledPlacementRefundsExactSeedAndDoesNotChangeDrops(GameTestHelper h) {
        ServerPlayer player = player(h);
        ItemStack namedSeed = new ItemStack(Items.WHEAT_SEEDS, 1);
        namedSeed.set(DataComponents.CUSTOM_NAME, Component.literal("Reserved seed"));
        player.getInventory().setItem(1, namedSeed);
        ItemStack originalSeed = namedSeed.copy();
        plant(h, CROP, mature(Blocks.WHEAT));
        CancellationProbe reject = new CancellationProbe(player);
        reject.cancelPlace = true;
        DropProbe drops = new DropProbe(player);
        NeoForge.EVENT_BUS.register(reject);
        NeoForge.EVENT_BUS.register(drops);
        try {
            player.gameMode.destroyBlock(h.absolutePos(CROP));
            RootedEnchantmentEvents.finishHarvests(h.getLevel());
            h.assertTrue(reject.placeCalls == 1 && h.getLevel().getBlockState(h.absolutePos(CROP)).isAir(),
                    "A normal placement protection hook must veto Rooted and restore the empty cell");
            h.assertTrue(ItemStack.matches(player.getInventory().getItem(1), originalSeed),
                    "Rejected placement must refund the exact reserved seed including all components");
            drops.assertUnchanged(h);
        } finally {
            NeoForge.EVENT_BUS.unregister(reject);
            NeoForge.EVENT_BUS.unregister(drops);
        }
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "rooted", skyAccess = true, setupTicks = 5L)
    public static void disabledAndCreativeHarvestNeverCreateFreePlants(GameTestHelper h) {
        ServerPlayer player = player(h);
        player.getInventory().setItem(1, new ItemStack(Items.WHEAT_SEEDS, 3));
        boolean original = AsobibaTweaksConfig.ROOTED_ENABLED.getAsBoolean();
        try {
            AsobibaTweaksConfig.ROOTED_ENABLED.set(false);
            plant(h, CROP, mature(Blocks.WHEAT));
            player.gameMode.destroyBlock(h.absolutePos(CROP));
            RootedEnchantmentEvents.finishHarvests(h.getLevel());
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).isAir(), "Disabled feature must leave harvest vanilla");
        } finally {
            AsobibaTweaksConfig.ROOTED_ENABLED.set(original);
        }
        player.gameMode.changeGameModeForPlayer(GameType.CREATIVE);
        plant(h, CROP, mature(Blocks.WHEAT));
        player.gameMode.destroyBlock(h.absolutePos(CROP));
        RootedEnchantmentEvents.finishHarvests(h.getLevel());
        h.assertTrue(h.getLevel().getBlockState(h.absolutePos(CROP)).isAir()
                && player.getInventory().getItem(1).getCount() == 3, "Creative breaking must neither create a crop nor charge inventory");
        h.succeed();
    }

    private static ServerPlayer player(GameTestHelper h) {
        // The vanilla helper hardcodes isCreative() to true. Reuse its embedded
        // connection setup with an ordinary ServerPlayer whose game mode is real.
        CommonListenerCookie cookie = CommonListenerCookie.createInitial(
                new GameProfile(UUID.randomUUID(), "rooted-test"), false);
        ServerPlayer player = new ServerPlayer(h.getLevel().getServer(), h.getLevel(),
                cookie.gameProfile(), cookie.clientInformation());
        Connection connection = new Connection(PacketFlow.SERVERBOUND);
        new EmbeddedChannel(connection);
        h.getLevel().getServer().getPlayerList().placeNewPlayer(connection, player, cookie);
        player.gameMode.changeGameModeForPlayer(GameType.SURVIVAL);
        player.getAbilities().mayBuild = true;
        player.setItemInHand(InteractionHand.MAIN_HAND, enchanted(h, Items.DIAMOND_HOE));
        Vec3 at = h.absoluteVec(new Vec3(3.5D, 2.0D, 5.5D));
        player.setPos(at.x, at.y, at.z);
        return player;
    }

    private static ItemStack enchanted(GameTestHelper h, Item item) {
        ItemStack stack = new ItemStack(item);
        stack.enchant(h.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(NewEnchantments.ROOTED), 1);
        return stack;
    }

    private static void plant(GameTestHelper h, BlockPos local, BlockState crop) {
        h.setBlock(local.below(), Blocks.FARMLAND);
        h.setBlock(local, crop);
    }

    private static BlockState mature(Block block) {
        CropBlock crop = (CropBlock)block;
        return crop.getStateForAge(crop.getMaxAge());
    }

    public static final class CancellationProbe {
        final ServerPlayer player;
        boolean cancelBreak, cancelDrops, cancelPlace;
        int placeCalls;
        CancellationProbe(ServerPlayer player) { this.player = player; }
        @SubscribeEvent(priority = EventPriority.LOWEST)
        public void breakBlock(BlockEvent.BreakEvent event) {
            if (event.getPlayer() == player && cancelBreak) event.setCanceled(true);
        }
        @SubscribeEvent(priority = EventPriority.LOWEST)
        public void drops(BlockDropsEvent event) {
            if (event.getBreaker() == player && cancelDrops) event.setCanceled(true);
        }
        @SubscribeEvent(priority = EventPriority.LOWEST)
        public void place(BlockEvent.EntityPlaceEvent event) {
            if (event.getEntity() == player) {
                placeCalls++;
                if (cancelPlace) event.setCanceled(true);
            }
        }
    }

    public static final class DropProbe {
        final ServerPlayer player;
        BlockDropsEvent event;
        List<ItemStack> before = new ArrayList<>();
        int experience;
        DropProbe(ServerPlayer player) { this.player = player; }
        @SubscribeEvent(priority = EventPriority.LOWEST)
        public void capture(BlockDropsEvent event) {
            if (event.getBreaker() != player) return;
            this.event = event;
            before = event.getDrops().stream().map(drop -> drop.getItem().copy()).toList();
            experience = event.getDroppedExperience();
        }
        void assertUnchanged(GameTestHelper h) {
            h.assertTrue(event != null && event.getDrops().size() == before.size()
                    && event.getDroppedExperience() == experience, "Rooted must preserve actual loot list and XP");
            for (int i = 0; i < before.size(); i++) {
                var drop = event.getDrops().get(i);
                h.assertTrue(ItemStack.matches(before.get(i), drop.getItem()) && !drop.isRemoved(),
                        "Each normal harvested drop must remain real, unmodified and spawned");
            }
        }
    }
}
