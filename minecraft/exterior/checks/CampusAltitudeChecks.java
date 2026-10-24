package dev.realworldmc.client;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;

/** Fresh airborne load, ascent/descent and an outside-coverage camera. QA only. */
public final class CampusAltitudeChecks {
    public static final String INITIAL_CAMERA="151 150 -116 90 58";
    private static final String[] CAMERAS={INITIAL_CAMERA,"151 65 -116 90 -12","151 100 -116 90 30","151 125 -116 90 48",INITIAL_CAMERA,"151 175 -116 90 66",INITIAL_CAMERA,"151 125 -116 90 48","151 100 -116 90 30","151 65 -116 90 -12","500 180 -116 90 14",INITIAL_CAMERA};
    private static final String[] LABELS={"airborne-start","ground","ascending-100","ascending-125","ascending-150","ascending-175","descending-150","descending-125","descending-100","ground-return","outside-coverage","airborne-return"};
    private static int phase,ticks;
    private static final JsonArray frames=new JsonArray(),fps=new JsonArray();
    public static void tick(Minecraft mc)throws Exception {
        // The enclosing check requires all selected tiles uploaded. Settle again
        // after each teleport, so old-camera readiness cannot certify this view.
        ticks++;if(ticks%20==0)fps.add(mc.getFps());if(ticks<200)return;
        var renderer=MapRenderer.INSTANCE;
        var lf=MapRenderer.class.getDeclaredField("loaded");lf.setAccessible(true);
        var df=MapRenderer.class.getDeclaredField("displayed");df.setAccessible(true);
        var loaded=(Map<?,?>)lf.get(renderer);var shown=(List<?>)df.get(renderer);
        var required=JsonParser.parseString(Files.readString(Path.of("altitude-required-tiles.json"))).getAsJsonArray();
        var absent=new JsonArray();for(var id:required)if(!shown.contains(id.getAsInt()))absent.add(id);
        var ids=new JsonArray();long triangles=0;int sourceAerial=0;
        for(var item:shown){int id=(Integer)item;ids.add(id);if(id>=1_300_000_000)sourceAerial++;var tile=(MapTile)loaded.get(id);for(var part:tile.data.parts)triangles+=part.triangleCount();}
        boolean strict=Boolean.getBoolean("minecampus.requireAltitudeContinuity");
        if(strict&&(!absent.isEmpty()||sourceAerial>0))throw new AssertionError("Altitude scene reverted at "+LABELS[phase]+": missing "+absent+", aerial source tiles "+sourceAerial);
        var row=new JsonObject();row.addProperty("phase",phase);row.addProperty("label",LABELS[phase]);row.addProperty("commandCamera",CAMERAS[phase]);row.addProperty("playerPosition",mc.player.position().toString());row.addProperty("triangles",triangles);row.add("fpsSamples",fps.deepCopy());row.add("displayedIds",ids);row.add("missingReconstructionIds",absent);row.addProperty("sourceAerialTiles",sourceAerial);
        String name="campus-altitude-"+phase+"-"+LABELS[phase]+".png";row.addProperty("capture",name);
        try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of(name));}
        frames.add(row);var report=new JsonObject();report.addProperty("status",phase==CAMERAS.length-1?(strict?"PASS: surveyed scene retained through airborne startup, ascent, descent and outside-camera views":"PASS: preceding-artifact altitude baseline captured"):"RUNNING");report.addProperty("rendererJar",Path.of(MapRenderer.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getFileName().toString());report.addProperty("requiredTileCount",required.size());report.add("frames",frames);
        Files.writeString(Path.of("campus-altitude-result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        if(++phase==CAMERAS.length){mc.stop();return;}
        ticks=0;fps.asList().clear();String camera=CAMERAS[phase];var uuid=mc.player.getUUID();
        mc.getSingleplayerServer().execute(()->{var player=mc.getSingleplayerServer().getPlayerList().getPlayer(uuid);mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s "+camera);});
    }
}
