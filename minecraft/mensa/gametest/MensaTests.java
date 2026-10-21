package dev.realworldmc;

import net.fabricmc.fabric.api.gametest.v1.FabricGameTest;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.phys.AABB;

/** Isolated native Minecraft validation; never enters the user's campus save. */
public final class MensaTests implements FabricGameTest {
    @GameTest(template=EMPTY_STRUCTURE, timeoutTicks=200)
    public void mensaTemplateAndTravel(GameTestHelper test) throws Exception {
        var server = test.getLevel().getServer();
        var id = ResourceLocation.fromNamespaceAndPath("minecampus_mensa", "study");
        var study = server.getLevel(ResourceKey.create(Registries.DIMENSION, id));
        test.assertTrue(study != null, "Mensa dimension JSON must register in Minecraft");
        for (String name : new String[]{"load", "visit", "capture", "prepare", "assemble", "back", "return_position"}) {
            test.assertTrue(server.getFunctions().get(ResourceLocation.fromNamespaceAndPath("minecampus_mensa", name)).isPresent(),
                "Minecraft must load function: " + name);
        }
        // Exercise the actual template loader, block registry and /place command.
        for (int x=-1; x<=6; x++) for (int z=-1; z<=6; z++) study.getChunk(x,z);
        var source = server.createCommandSourceStack().withLevel(study);
        int result = server.getCommands().getDispatcher().execute("place template minecampus_mensa:mensa -10 64 -10", source);
        test.assertTrue(result > 0, "Mensa NBT must place using Minecraft's template command");
        test.assertTrue(study.getBlockState(new BlockPos(48,65,73)).getBlock() instanceof DoorBlock,
            "Main entry must be a usable native Minecraft door");
        test.assertTrue(study.getBlockState(new BlockPos(48,65,74)).is(Blocks.BIRCH_PRESSURE_PLATE),
            "Entry must have a functioning native pressure plate");
        test.assertTrue(study.getBlockState(new BlockPos(49,67,56)).is(Blocks.SMOOTH_QUARTZ_STAIRS),
            "Foyer stair must reach the upper storey");
        test.assertTrue(study.getBlockState(new BlockPos(49,70,56)).isAir(),
            "Upper slab must not obstruct the ascending staircase");
        test.assertTrue(study.getBlockState(new BlockPos(30,78,45)).isAir(),
            "Central courtyard must stay open through the roof");
        test.assertTrue(study.getBlockState(new BlockPos(60,78,40)).is(Blocks.SMOOTH_STONE),
            "Dining hall needs a real roof around the courtyard");
        var food = study.getBlockEntity(new BlockPos(19,71,16));
        test.assertTrue(food instanceof net.minecraft.world.Container, "Food station must be an actual container");
        test.assertTrue(((net.minecraft.world.Container)food).getItem(0).getCount()==32,
            "Minecraft must read the 1.21 item-stack NBT in the food barrel");
        var door = new BlockPos(49,65,73);
        study.setBlockAndUpdate(door, study.getBlockState(door).setValue(DoorBlock.OPEN,true));
        for (double[] point : new double[][]{
            {49.5,65,84.5}, {49.5,65.0625,73.5}, {49.5,65,65.5},
            {49.5,71,52.5}, {54.5,71,40.5}, {11.5,65,43.5}, {30.5,65,57.5}
        }) {
            test.assertTrue(study.noCollision(null, new AABB(point[0]-.3,point[1]+.001,point[2]-.3,
                point[0]+.3,point[1]+1.8,point[2]+.3)), "Player body must fit at walk-through point " + java.util.Arrays.toString(point));
        }
        // Run the shipped functions with a mock player, including the return-position macro.
        var player = test.makeMockServerPlayerInLevel();
        player.teleportTo(-123.45,100,234.56);
        player.setYRot(37); player.setXRot(-12);
        server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),
            "function minecampus_mensa:load");
        var start = player.position();
        server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),
            "function minecampus_mensa:visit");
        test.assertTrue(player.serverLevel()==study, "Visit must enter the native Mensa dimension");
        server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),
            "function minecampus_mensa:back");
        test.assertTrue(player.serverLevel()==test.getLevel(), "Back must return to the original Overworld");
        test.assertTrue(player.position().distanceTo(start)<0.025, "Return must retain the player's own coordinates");
        test.assertTrue(Math.abs(player.getYRot()-37)<0.02 && Math.abs(player.getXRot()+12)<0.02,
            "Return must retain the camera direction");
        test.succeed();
    }
}
