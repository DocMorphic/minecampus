package dev.realworldmc.client;

import com.google.gson.*;
import dev.realworldmc.*;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.item.Items;
import java.util.concurrent.TimeUnit;

/** Optional assertions for a prepared copy of an older isolated QA save. */
public final class CampusMigrationCheck {
    private CampusMigrationCheck() {}
    public static JsonObject check(Minecraft mc, JsonObject spec) throws Exception {
        if(!Boolean.getBoolean("minecampus.siteInspection"))throw new AssertionError("Migration check requires isolated site inspection");
        return mc.getSingleplayerServer().submit(() -> {
            var level=mc.getSingleplayerServer().overworld();
            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
            for(var item:spec.getAsJsonArray("cells")){
                var p=item.getAsJsonObject().getAsJsonArray("position");
                if(!CampusCollision.aligned(level,p.get(0).getAsInt()>>4,p.get(2).getAsInt()>>4))return null;
            }
            var rows=new JsonArray();
            for(var item:spec.getAsJsonArray("cells")){
                var control=item.getAsJsonObject();var p=control.getAsJsonArray("position");
                var pos=new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt());
                var actual=level.getBlockState(pos);String name=BuiltInRegistries.BLOCK.getKey(actual.getBlock()).toString();
                if(control.has("code")){
                    if(actual!=EarthBlocks.byCode(control.get("code").getAsInt()))throw new AssertionError("Old ground did not migrate at "+pos+": "+actual);
                }else if(!name.equals(control.get("block").getAsString()))throw new AssertionError("Saved edit changed at "+pos+": "+actual);
                var row=control.deepCopy();row.addProperty("actualState",actual.toString());rows.add(row);
            }
            var edits=MapEdits.storage(level);
            if(edits.original.size()!=spec.get("recordedEdits").getAsInt())throw new AssertionError("Migration changed the edit journal");
            for(var item:spec.getAsJsonArray("recordedPositions")){
                var p=item.getAsJsonArray();var pos=new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt());
                if(!edits.original.containsKey(pos.asLong()))throw new AssertionError("Migration lost edit history at "+pos);
            }
            var inventory=player.getInventory();int occupied=0;
            for(int i=0;i<inventory.getContainerSize();i++)if(!inventory.getItem(i).isEmpty())occupied++;
            if(occupied!=1||!inventory.getItem(0).is(Items.DIAMOND)||inventory.getItem(0).getCount()!=42||player.experienceLevel!=17)
                throw new AssertionError("Saved inventory or experience changed");
            var report=new JsonObject();report.addProperty("status","PASS: old saved ground migrated; placed block, recorded removals, inventory and experience retained");
            report.add("cells",rows);report.addProperty("recordedEdits",edits.original.size());report.addProperty("inventoryDiamonds",inventory.getItem(0).getCount());report.addProperty("experienceLevel",player.experienceLevel);return report;
        }).get(30,TimeUnit.SECONDS);
    }
}
