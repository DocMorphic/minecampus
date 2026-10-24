package dev.realworldmc.client;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;

/** QA-only, source-study cameras and optional surface controls in an isolated world. */
public final class CampusSiteInspection {
    private static JsonObject plan;
    private static int phase, ticks;
    private static final JsonArray frames = new JsonArray();

    private static JsonArray cameras() throws Exception {
        if (plan == null) {
            plan = JsonParser.parseString(Files.readString(Path.of("site-inspection.json"))).getAsJsonObject();
            if (!plan.get("name").getAsString().matches("[a-z0-9-]+")) throw new IllegalArgumentException("Invalid inspection name");
            if (plan.getAsJsonArray("cameras").isEmpty()) throw new IllegalArgumentException("No inspection cameras");
        }
        return plan.getAsJsonArray("cameras");
    }

    public static String initialCamera() throws Exception {
        return cameras().get(0).getAsJsonObject().get("position").getAsString();
    }

    private static JsonArray probe(Minecraft mc, Map<?, ?> loaded, List<?> displayed, JsonArray controls) {
        var results = new JsonArray();
        for (var entry : controls) {
            var control = entry.getAsJsonObject();
            var p = control.getAsJsonArray("target"); var n = control.getAsJsonArray("normal");
            double x=p.get(0).getAsDouble(), y=p.get(1).getAsDouble(), z=p.get(2).getAsDouble();
            double nx=n.get(0).getAsDouble(), ny=n.get(1).getAsDouble(), nz=n.get(2).getAsDouble();
            float distance=1000, firstDistance=1000; int hit=-1, part=-1, firstHit=-1;
            for (var value : loaded.values()) {
                var data=((MapTile)value).data;
                if (!displayed.contains(data.id)) continue;
                boolean vegetation=plan.has("vegetationTileIds") && plan.getAsJsonArray("vegetationTileIds").contains(new JsonPrimitive(data.id));
                for (int pi=0; pi<data.parts.length; pi++) {
                    var v=data.parts[pi].vertices;
                    for (int o=0; o<v.length; o+=15) {
                        float t=org.joml.Intersectionf.intersectRayTriangle((float)(x+nx*.6-data.anchorX),(float)(y+ny*.6-data.anchorY),(float)(z+nz*.6-data.anchorZ),
                            (float)-nx,(float)-ny,(float)-nz,v[o],v[o+1],v[o+2],v[o+5],v[o+6],v[o+7],v[o+10],v[o+11],v[o+12],1e-6f);
                        if (t>0 && t<firstDistance) { firstDistance=t; firstHit=data.id; }
                        if (!vegetation && t>0 && t<distance) { distance=t; hit=data.id; part=pi; }
                    }
                }
            }
            if (hit!=control.get("tile").getAsInt() || part!=control.get("part").getAsInt() || Math.abs(distance-.6)>.025)
                throw new AssertionError("Inspection surface missing/obstructed at "+x+","+y+","+z+": "+hit+"/"+part+" distance "+distance);
            var row=control.deepCopy(); row.addProperty("hitTile",hit); row.addProperty("hitPart",part); row.addProperty("distance",distance);
            row.addProperty("firstHitTile",firstHit); row.addProperty("firstHitDistance",firstDistance);
            if (control.has("collider") && control.get("collider").getAsBoolean()) {
                var from=new net.minecraft.world.phys.Vec3(x+nx*1.6,y,z+nz*1.6);
                var to=new net.minecraft.world.phys.Vec3(x-nx*.6,y,z-nz*.6);
                var collision=mc.level.clip(new net.minecraft.world.level.ClipContext(from,to,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
                if (collision.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK || !dev.realworldmc.EarthBlocks.isMapBlock(mc.level.getBlockState(collision.getBlockPos())))
                    throw new AssertionError("Inspection wall lacks native collision at "+x+","+y+","+z);
                row.addProperty("nativeCollider",collision.getBlockPos().toShortString());
            }
            results.add(row);
        }
        return results;
    }

    public static void tick(Minecraft mc) throws Exception {
        // Called only while the parent reports full streaming/upload readiness.
        // Wait again at each position rather than using the prior camera's state.
        if (++ticks < 200) return;
        var cameras = cameras();
        var camera = cameras.get(phase).getAsJsonObject();
        var loadedField = MapRenderer.class.getDeclaredField("loaded");
        var displayedField = MapRenderer.class.getDeclaredField("displayed");
        loadedField.setAccessible(true); displayedField.setAccessible(true);
        var loaded = (Map<?, ?>) loadedField.get(MapRenderer.INSTANCE);
        var displayed = (List<?>) displayedField.get(MapRenderer.INSTANCE);
        var ids = new JsonArray(); long triangles = 0;
        for (var id : displayed) {
            ids.add((Integer) id);
            for (var part : ((MapTile) loaded.get(id)).data.parts) triangles += part.triangleCount();
        }
        String name = "campus-" + plan.get("name").getAsString() + "-" + phase + ".png";
        try (var image = Screenshot.takeScreenshot(mc.getMainRenderTarget())) { image.writeToFile(Path.of(name)); }
        var row = camera.deepCopy();
        row.addProperty("capture", name); row.addProperty("playerPosition", mc.player.position().toString());
        row.addProperty("triangles", triangles); row.add("displayedIds", ids);
        if (camera.has("probes")) row.add("probes", probe(mc, loaded, displayed, camera.getAsJsonArray("probes")));
        frames.add(row);
        var report = new JsonObject();
        report.addProperty("status", phase == cameras.size() - 1 ? "PASS: inspection cameras captured; visual assessment required" : "RUNNING");
        report.addProperty("rendererJar", Path.of(MapRenderer.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getFileName().toString());
        report.add("plan", plan); report.add("frames", frames);
        Files.writeString(Path.of("campus-" + plan.get("name").getAsString() + "-result.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
        if (++phase == cameras.size()) { mc.stop(); return; }
        ticks = 0; String next = cameras.get(phase).getAsJsonObject().get("position").getAsString();
        var uuid = mc.player.getUUID();
        mc.getSingleplayerServer().execute(() -> {
            var player = mc.getSingleplayerServer().getPlayerList().getPlayer(uuid);
            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4), "tp @s " + next);
        });
    }
}
