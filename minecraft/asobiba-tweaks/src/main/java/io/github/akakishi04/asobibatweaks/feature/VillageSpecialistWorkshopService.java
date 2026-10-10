package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/**
 * Profession-driven, physical workstation halls built by actual Carpenters.
 *
 * A missing job site is observed on a loaded resident. Planning requires a
 * genuine finished station item in recognized local village storage. Shell
 * blocks, furnishings and storage are paid for incrementally as physical
 * cargo during the normal durable building project; no workstation is minted.
 *
 * Distinct gabled library, stone-roof industrial, and ventilated open market
 * shells are chosen from the profession, rather than one repeated façade.
 */
public final class VillageSpecialistWorkshopService {
    private enum Style { GABLED, STONE_ROOF, VENTILATED }

    private record Family(String template, VillagerProfession profession,
                          Block workstation, Style style) {}

    private static final List<Family> FAMILIES = List.of(
            new Family("village_library_5x5", VillagerProfession.LIBRARIAN,
                    Blocks.LECTERN, Style.GABLED),
            new Family("village_armory_5x5", VillagerProfession.ARMORER,
                    Blocks.BLAST_FURNACE, Style.STONE_ROOF),
            new Family("village_fishery_5x5", VillagerProfession.FISHERMAN,
                    Blocks.BARREL, Style.VENTILATED),
            new Family("village_cartographer_5x5", VillagerProfession.CARTOGRAPHER,
                    Blocks.CARTOGRAPHY_TABLE, Style.GABLED),
            new Family("village_cleric_5x5", VillagerProfession.CLERIC,
                    Blocks.BREWING_STAND, Style.STONE_ROOF),
            new Family("village_shepherd_5x5", VillagerProfession.SHEPHERD,
                    Blocks.LOOM, Style.VENTILATED),
            new Family("village_fletcher_5x5", VillagerProfession.FLETCHER,
                    Blocks.FLETCHING_TABLE, Style.GABLED),
            new Family("village_butcher_5x5", VillagerProfession.BUTCHER,
                    Blocks.SMOKER, Style.STONE_ROOF),
            new Family("village_leatherworker_5x5", VillagerProfession.LEATHERWORKER,
                    Blocks.CAULDRON, Style.VENTILATED),
            new Family("village_weaponsmith_5x5", VillagerProfession.WEAPONSMITH,
                    Blocks.GRINDSTONE, Style.STONE_ROOF),
            new Family("village_farmhouse_5x5", VillagerProfession.FARMER,
                    Blocks.COMPOSTER, Style.VENTILATED)
    );
    private static final int MAX_PER_PROFESSION = 2;

    private VillageSpecialistWorkshopService() {}

    public static String neededTemplate(
            Villager carpenter, ServerLevel level, VillageSavedData data, UUID villageId) {
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return "";

        List<Villager> missingSites = level.getEntitiesOfClass(Villager.class,
                VillageActivityBoundary.searchBounds(village),
                v -> v.isAlive() && VillageActivityBoundary.contains(village, v.blockPosition()) && !v.isBaby()
                        && VillagerSimData.villageId(v).filter(villageId::equals).isPresent()
                        && !v.getBrain().hasMemoryValue(MemoryModuleType.JOB_SITE));
        if (missingSites.isEmpty()) return "";

        for (Family family : FAMILIES) {
            int workers = (int)missingSites.stream()
                    .filter(v -> v.getVillagerData().getProfession() == family.profession())
                    .count();
            if (workers == 0) continue;
            int target = Math.min(MAX_PER_PROFESSION, (workers + 1) / 2);
            long finished = village.buildingIds().stream()
                    .map(data::building).flatMap(java.util.Optional::stream)
                    .filter(b -> family.template().equals(b.templateId())
                            && "valid".equals(b.validationState())).count();
            long active = data.activeProjectsForVillage(villageId).stream()
                    .filter(p -> family.template().equals(p.templateId())).count();
            if (finished + active >= target) continue;

            Item item = family.workstation().asItem();
            int stock = VillageStorageService.count(carpenter, level, item)
                    + VillagerSimData.workCargoCount(carpenter,
                            level.registryAccess(), 8, item);
            if (stock <= 0 && !hasRealRecipeInputs(carpenter, level, item)) {
                // An uncraftable/unsupplied station is not a real build need:
                // do not reserve a building shell whose job site cannot exist.
                continue;
            }
            return family.template();
        }
        return "";
    }

    private static boolean hasRealRecipeInputs(
            Villager carpenter, ServerLevel level, Item workstation) {
        int planks = VillageStorageService.count(carpenter, level,
                Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS,
                Items.JUNGLE_PLANKS, Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS,
                Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS);
        if (workstation == Items.BARREL || workstation == Items.COMPOSTER)
            return planks >= 12;
        if (workstation == Items.LOOM)
            return planks >= 2 && VillageStorageService.count(
                    carpenter, level, Items.STRING) >= 2;
        if (workstation == Items.FLETCHING_TABLE)
            return planks >= 4 && VillageStorageService.count(
                    carpenter, level, Items.FLINT) >= 2;
        if (workstation == Items.CARTOGRAPHY_TABLE)
            return planks >= 4 && VillageStorageService.count(
                    carpenter, level, Items.PAPER) >= 2;
        if (workstation == Items.CAULDRON)
            return VillageStorageService.count(
                    carpenter, level, Items.IRON_INGOT) >= 7;
        if (workstation == Items.BREWING_STAND)
            return VillageStorageService.count(
                    carpenter, level, Items.BLAZE_ROD) >= 1
                    && VillageStorageService.count(
                            carpenter, level, Items.COBBLESTONE) >= 3;
        if (workstation == Items.BLAST_FURNACE)
            return VillageStorageService.count(carpenter, level, Items.FURNACE) >= 1
                    && VillageStorageService.count(
                            carpenter, level, Items.IRON_INGOT) >= 5
                    && VillageStorageService.count(
                            carpenter, level, Items.SMOOTH_STONE) >= 3;
        if (workstation == Items.SMOKER)
            return VillageStorageService.count(carpenter, level, Items.FURNACE) >= 1
                    && VillageStorageService.count(carpenter, level,
                            Items.OAK_LOG, Items.SPRUCE_LOG, Items.BIRCH_LOG,
                            Items.JUNGLE_LOG, Items.ACACIA_LOG, Items.DARK_OAK_LOG,
                            Items.MANGROVE_LOG, Items.CHERRY_LOG) >= 4;
        if (workstation == Items.GRINDSTONE)
            return planks >= 2
                    && VillageStorageService.count(carpenter, level, Items.STICK) >= 2
                    && (VillageStorageService.count(
                            carpenter, level, Items.STONE_SLAB) >= 1
                            || VillageStorageService.count(
                                    carpenter, level, Items.STONE) >= 3);
        if (workstation == Items.LECTERN) {
            boolean bookshelf = VillageStorageService.count(
                    carpenter, level, Items.BOOKSHELF) > 0
                    || (planks >= 9
                            && (VillageStorageService.count(
                                    carpenter, level, Items.BOOK) >= 3
                                    || VillageStorageService.count(
                                            carpenter, level, Items.PAPER) >= 9
                                        && VillageStorageService.count(
                                            carpenter, level, Items.LEATHER) >= 3));
            return planks >= 3 && bookshelf;
        }
        return false;
    }

    public static boolean isSpecialistTemplate(String name) {
        return family(name) != null;
    }

    public static boolean hasGabledRoof(String name) {
        Family f = family(name);
        return f != null && f.style() == Style.GABLED;
    }

    public static Block primaryStation(String template) {
        Family f = family(template);
        return f == null ? null : f.workstation();
    }

    public static List<VillageSimulationEvents.BuildStep> plan(
            VillageSavedData.ProjectRecord project,
            List<VillageSimulationEvents.BuildStep> storageShell) {
        Family f = family(project.templateId());
        if (f == null) return List.of();
        BlockPos base = project.site();
        List<VillageSimulationEvents.BuildStep> steps = new ArrayList<>(storageShell);
        // The shell's default pair of Barrels belongs to a warehouse. Each
        // specialist hall instead gets exactly one job-site station and one
        // dedicated publicly recognized real storage Barrel.
        steps.removeIf(s -> s.state().is(Blocks.BARREL));

        Block roofPlank = switch (project.parameter("plank")) {
            case "spruce" -> Blocks.SPRUCE_PLANKS;
            case "birch" -> Blocks.BIRCH_PLANKS;
            case "jungle" -> Blocks.JUNGLE_PLANKS;
            case "acacia" -> Blocks.ACACIA_PLANKS;
            case "dark_oak" -> Blocks.DARK_OAK_PLANKS;
            case "mangrove" -> Blocks.MANGROVE_PLANKS;
            case "cherry" -> Blocks.CHERRY_PLANKS;
            default -> Blocks.OAK_PLANKS;
        };
        if (f.style() == Style.GABLED) {
            steps.removeIf(s -> s.pos().getY() == base.getY() + 4);
            BlockState plank = roofPlank.defaultBlockState();
            Item material = roofPlank.asItem();
            for (int z = 0; z < 5; z++) {
                for (int x : new int[]{0, 4}) {
                    steps.add(new VillageSimulationEvents.BuildStep(
                            base.offset(x, 4, z), plank, material));
                }
                for (int x : new int[]{1, 3}) {
                    steps.add(new VillageSimulationEvents.BuildStep(
                            base.offset(x, 5, z), plank, material));
                }
                steps.add(new VillageSimulationEvents.BuildStep(
                        base.offset(2, 6, z), plank, material));
            }
        } else if (f.style() == Style.STONE_ROOF) {
            steps.removeIf(s -> s.pos().getY() == base.getY() + 4
                    || isWallCorner(base, s.pos()));
            for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                steps.add(new VillageSimulationEvents.BuildStep(
                        base.offset(x, 4, z),
                        Blocks.COBBLESTONE.defaultBlockState(), Items.COBBLESTONE));
            }
            for (int y = 1; y <= 3; y++) for (int x : new int[]{0, 4})
                    for (int z : new int[]{0, 4}) {
                steps.add(new VillageSimulationEvents.BuildStep(
                        base.offset(x, y, z),
                        Blocks.COBBLESTONE.defaultBlockState(), Items.COBBLESTONE));
            }
        } else {
            // Open, well-ventilated fishing/farming/work shed. The two window
            // apertures remain clear: they are intentional absent blocks,
            // never invisible free glass or a fake protected entrance.
            steps.removeIf(s -> s.pos().getY() == base.getY() + 2
                    && (s.pos().getX() == base.getX()
                            || s.pos().getX() == base.getX() + 4)
                    && s.pos().getZ() == base.getZ() + 2);
        }

        steps.add(new VillageSimulationEvents.BuildStep(
                base.offset(2, 1, 2), f.workstation().defaultBlockState(),
                f.workstation().asItem()));
        steps.add(new VillageSimulationEvents.BuildStep(
                base.offset(3, 1, 3), Blocks.BARREL.defaultBlockState(), Items.BARREL));
        return List.copyOf(steps);
    }

    private static boolean isWallCorner(BlockPos base, BlockPos pos) {
        return pos.getY() > base.getY() && pos.getY() <= base.getY() + 3
                && (pos.getX() == base.getX() || pos.getX() == base.getX() + 4)
                && (pos.getZ() == base.getZ() || pos.getZ() == base.getZ() + 4);
    }

    private static Family family(String template) {
        if (template == null) return null;
        for (Family family : FAMILIES) {
            if (family.template().equals(template)) return family;
        }
        return null;
    }
}
