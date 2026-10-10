package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.common.damagesource.DamageContainer;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class FeatherFallingMasteryGameTests {
    private static final BlockPos MARK = new BlockPos(4, 2, 4);
    private FeatherFallingMasteryGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "feather_mastery")
    public static void featherBranchesSelectStrongestPerBranchAndCapAt100(GameTestHelper helper) {
        var armor = List.of(boots(helper, 50, 0), boots(helper, 100, 0),
                boots(helper, 75, 1), boots(helper, 500, 2));
        if (FeatherFallingMasteryEvents.strongestMastery(armor, 0) != 100
                || FeatherFallingMasteryEvents.strongestMastery(armor, 1) != 75
                || FeatherFallingMasteryEvents.strongestMastery(armor, 2) != 100
                || Math.abs(FeatherFallingMasteryEvents.softReduction(50) - 0.1D) > 0.00001D
                || Math.abs(FeatherFallingMasteryEvents.softReduction(500) - 0.3D) > 0.00001D
                || FeatherFallingMasteryEvents.impactRadius(50) != 2.0D
                || FeatherFallingMasteryEvents.impactRadius(100) != 4.0D
                || FeatherFallingMasteryEvents.impactDamage(1000.0D, 100) != 6.0D
                || FeatherFallingMasteryEvents.attributablePrevention(8.0D, 32.0D, 12.0D) != 0.0D) {
            helper.fail("Feather mastery stacking, scaling or ordinary protection attribution is wrong", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "feather_mastery")
    public static void softLandingUsesRemainingDamageAndNeverStacksDuplicates(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        player.setItemSlot(EquipmentSlot.FEET, boots(helper, 100, 0));
        player.setItemSlot(EquipmentSlot.HEAD, boots(helper, 100, 0));
        DamageContainer damage = new DamageContainer(helper.getLevel().damageSources().fall(), 20.0F);
        damage.setNewDamage(10.0F); // Snapshot after vanilla armor/enchantment mitigation.
        var event = new LivingDamageEvent.Pre(player, damage);
        new FeatherFallingMasteryEvents().onFallDamage(event);
        if (Math.abs(event.getNewDamage() - 7.0F) > 0.0001F) {
            helper.fail("Soft Landing must remove 30% once from remaining fall damage", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "feather_mastery")
    public static void impactLandingUsesRealFeatherPrevention(GameTestHelper helper) {
        var level = helper.getLevel();
        var player = helper.makeMockServerPlayerInLevel();
        // The built-in mock is creative; exercise the ordinary survival fall path.
        player.getAbilities().mayfly = false;
        player.getAbilities().flying = false;
        player.getAbilities().invulnerable = false;
        player.getAbilities().instabuild = false;
        // ServerPlayer also has a native60-tick post-spawn immunity window.
        helper.runAfterDelay(61, () -> {
            BlockPos at = helper.absolutePos(MARK);
            player.setPos(at.getX() + 0.5D, at.getY(), at.getZ() + 0.5D);
            player.setItemSlot(EquipmentSlot.FEET, boots(helper, 100, 1));
            var pig = EntityType.PIG.create(level);
            if (pig == null) throw new IllegalStateException("Cannot create impact target");
            pig.setNoAi(true);
            pig.setPos(at.getX() + 1.5D, at.getY(), at.getZ() + 0.5D);
            if (!level.addFreshEntity(pig)) throw new IllegalStateException("Cannot spawn impact target");
            float before = pig.getHealth();
            // Real native fall pipeline: 8 blocks -> 5 incoming fall damage;
            // Feather Falling IV prevents 48% = 2.4; Impact 100 echoes 25% = 0.6.
            player.causeFallDamage(8.0F, 1.0F, level.damageSources().fall());
            float lost = before - pig.getHealth();
            pig.discard();
            if (Math.abs(lost - 0.6F) > 0.01F) {
                helper.fail("Landing shock must use only real Feather Falling prevention, got " + lost, MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "feather_mastery")
    public static void aerialRecoveryScalesRealInputWithoutChangingGravity(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        BlockPos at = helper.absolutePos(MARK);
        player.setPos(at.getX() + 0.5D, at.getY(), at.getZ() + 0.5D);
        player.setItemSlot(EquipmentSlot.FEET, boots(helper, 100, 2));
        player.setItemSlot(EquipmentSlot.HEAD, boots(helper, 100, 2));
        player.setYRot(0.0F);
        player.setOnGround(false);
        player.setDeltaMovement(0.0D, -0.5D, 0.0D);
        player.moveRelative(0.02F, new Vec3(0, 0, 1));
        Vec3 falling = player.getDeltaMovement();
        player.setOnGround(true);
        player.setDeltaMovement(0.0D, -0.5D, 0.0D);
        player.moveRelative(0.02F, new Vec3(0, 0, 1));
        if (Math.abs(falling.z - 0.027D) > 0.00001D || falling.y != -0.5D
                || Math.abs(player.getDeltaMovement().z - 0.02D) > 0.00001D) {
            helper.fail("Aerial Recovery must boost real airborne input 35% once, preserving vertical velocity", MARK);
            return;
        }
        helper.succeed();
    }

    private static ItemStack boots(GameTestHelper helper, int mastery, int branch) {
        ItemStack stack = new ItemStack(Items.DIAMOND_BOOTS);
        var enchantment = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FEATHER_FALLING);
        stack.enchant(enchantment, 4);
        EnchantmentMasteryData.addMastery(stack, enchantment, mastery);
        for (int i = 0; i <= branch; i++) EnchantmentMasteryData.cycleBranch(stack, enchantment);
        return stack;
    }
}
