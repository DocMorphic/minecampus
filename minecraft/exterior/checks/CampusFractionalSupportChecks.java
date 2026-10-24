package dev.realworldmc.client;

import com.google.gson.JsonObject;
import dev.realworldmc.EarthBlocks;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.RenderShape;

/** QA only: test the packaged block registry, shapes and saved-state compatibility. */
public final class CampusFractionalSupportChecks {
    public static JsonObject verify(Minecraft mc) {
        var registry=mc.level.registryAccess().lookupOrThrow(Registries.BLOCK);
        int states=0;
        for(int material=1;material<=9;material++){
            var full=EarthBlocks.byCode(material);
            if(full.getCollisionShape(mc.level,BlockPos.ZERO).max(Direction.Axis.Y)!=1)throw new AssertionError("Legacy full height");
            var oldTag=NbtUtils.writeBlockState(full);oldTag.remove("Properties");
            if(NbtUtils.readBlockState(registry,oldTag)!=full)throw new AssertionError("Legacy saved state default");
            for(int height=1;height<=16;height++){
                var state=EarthBlocks.byCode(32+(material-1)*16+height-1);
                if(state.getBlock()!=full.getBlock()||!EarthBlocks.isMapBlock(state))throw new AssertionError("Material identity changed");
                if(state.getRenderShape()!=RenderShape.INVISIBLE)throw new AssertionError("Visible proxy");
                if(state.getCollisionShape(mc.level,BlockPos.ZERO).max(Direction.Axis.Y)!=height/16.0)throw new AssertionError("Collision height");
                if(state.getShape(mc.level,BlockPos.ZERO).max(Direction.Axis.Y)!=height/16.0)throw new AssertionError("Selection height");
                if(NbtUtils.readBlockState(registry,NbtUtils.writeBlockState(state))!=state)throw new AssertionError("Saved height round trip");
                if(Block.stateById(Block.getId(state))!=state)throw new AssertionError("Network state round trip");
                if(EarthBlocks.cutMaterial(state)!=EarthBlocks.cutMaterial(full))throw new AssertionError("Mining material changed");
                states++;
            }
        }
        var result=new JsonObject();result.addProperty("status","PASS: native shape, saved-state, network-ID and cut-material checks");result.addProperty("states",states);result.addProperty("legacyDefaults",9);return result;
    }
}
