package dev.realworldmc.client;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;

/** QA-only, source-study cameras and optional surface controls in an isolated world. */
public final class CampusSiteInspection {
    private static JsonObject plan;
    private static JsonObject fractionalSupportChecks;
    private static JsonObject migrationChecks;
    private static boolean migrationCameraReturned;
    private static int phase, ticks;
    private static final JsonArray frames = new JsonArray();
    private static final JsonArray gravity = new JsonArray();
    private static volatile int gravityIndex;
    private static int gravityTicks;
    private static int gravityAlignmentWaitTicks;
    private static int gravityReportedIndex;
    private static volatile boolean gravityQueued, gravityReady, gravityChecking, gravityReleased;
    private static volatile Throwable gravityFailure;
    private static volatile JsonObject gravityFailureDetails;

    private static JsonArray cameras() throws Exception {
        if (plan == null) {
            plan = JsonParser.parseString(Files.readString(Path.of("site-inspection.json"))).getAsJsonObject();
            if (!plan.get("name").getAsString().matches("[a-z0-9-]+")) throw new IllegalArgumentException("Invalid inspection name");
            if (plan.getAsJsonArray("cameras").isEmpty()) throw new IllegalArgumentException("No inspection cameras");
        }
        return plan.getAsJsonArray("cameras");
    }

    public static String initialCamera() throws Exception {
        cameras();
        // A new alignment journal only visits chunks near the player. When the
        // matched route starts elsewhere, visit its saved-edit fixture first.
        if(plan.has("migration")&&plan.has("migrationCamera"))return plan.get("migrationCamera").getAsString();
        return cameras().get(0).getAsJsonObject().get("position").getAsString();
    }

    /** Migration does not depend on provider rendering; verify it once local chunks align. */
    public static void checkMigration(Minecraft mc) throws Exception {
        cameras();
        if(plan.has("migration")&&migrationChecks==null){
            migrationChecks=CampusMigrationCheck.check(mc,plan.getAsJsonObject("migration"));
            if(migrationChecks!=null){
                if(plan.has("migrationCamera")&&!migrationCameraReturned){
                    mc.player.connection.sendCommand("tp @s "+cameras().get(0).getAsJsonObject().get("position").getAsString());
                    migrationCameraReturned=true;ticks=0;
                }
                writeReport("RUNNING: saved-world migration verified; native views pending");
            }
        }
    }

    /** Optional private geometry diagnostic; no textures or provider credentials. */
    private static void recordSourceTriangles(Map<?, ?> loaded, List<?> displayed, String prefix) throws Exception {
        if (!plan.has("diagnosticBounds")) return;
        var bounds=plan.getAsJsonArray("diagnosticBounds");
        var low=bounds.get(0).getAsJsonArray(); var high=bounds.get(1).getAsJsonArray();
        var rows=new JsonArray();
        for (var value : loaded.values()) {
            var data=((MapTile)value).data;
            if (data.id<1_100_000_000 || !displayed.contains(data.id)) continue;
            for (int part=0;part<data.parts.length;part++) {
                var vertices=data.parts[part].vertices;
                for (int offset=0;offset<vertices.length;offset+=15) {
                    boolean inside=true;
                    double[] anchor={data.anchorX,data.anchorY,data.anchorZ};
                    for(int axis=0;axis<3;axis++){
                        double a=vertices[offset+axis]+anchor[axis],b=vertices[offset+5+axis]+anchor[axis],c=vertices[offset+10+axis]+anchor[axis];
                        inside&=Math.max(a,Math.max(b,c))>=low.get(axis).getAsDouble()&&Math.min(a,Math.min(b,c))<=high.get(axis).getAsDouble();
                    }
                    if(!inside)continue;
                    var row=new JsonObject();row.addProperty("tile",data.id);row.addProperty("part",part);var triangle=new JsonArray();
                    for(int vertex=0;vertex<3;vertex++){
                        var point=new JsonArray();point.add(data.anchorX+vertices[offset+vertex*5]);point.add(data.anchorY+vertices[offset+vertex*5+1]);point.add(data.anchorZ+vertices[offset+vertex*5+2]);triangle.add(point);
                    }
                    row.add("vertices",triangle);rows.add(row);
                }
            }
        }
        Files.writeString(Path.of(prefix+"-source-triangles.json"),new Gson().toJson(rows));
    }

    /** Diagnose visible pixels using the live camera projection, including FOV effects. */
    private static JsonArray screenRays(Minecraft mc, Map<?, ?> loaded, List<?> displayed, JsonArray controls) throws Exception {
        var camera=mc.gameRenderer.getMainCamera();var eye=camera.getPosition();
        var method=net.minecraft.client.renderer.GameRenderer.class.getDeclaredMethod("getFov",net.minecraft.client.Camera.class,float.class,boolean.class);method.setAccessible(true);
        double fov=(Double)method.invoke(mc.gameRenderer,camera,mc.getTimer().getGameTimeDeltaPartialTick(false),true);
        var inverse=new org.joml.Matrix4f(mc.gameRenderer.getProjectionMatrix(fov)).invert();var result=new JsonArray();
        for(var item:controls){
            var control=item.getAsJsonObject();double u=control.get("u").getAsDouble(),v=control.get("v").getAsDouble();
            var local=new org.joml.Vector4f((float)(u*2-1),(float)(1-v*2),-1,1).mul(inverse);
            var direction=new org.joml.Vector3f(local.x/local.w,local.y/local.w,local.z/local.w).normalize().rotate(camera.rotation());
            var hits=new ArrayList<JsonObject>();
            for(var value:loaded.values()){
                var data=((MapTile)value).data;if(!displayed.contains(data.id))continue;
                for(int part=0;part<data.parts.length;part++){
                    var vertices=data.parts[part].vertices;float nearest=Float.POSITIVE_INFINITY;int found=-1;
                    for(int offset=0;offset<vertices.length;offset+=15){
                        float distance=org.joml.Intersectionf.intersectRayTriangle((float)(eye.x-data.anchorX),(float)(eye.y-data.anchorY),(float)(eye.z-data.anchorZ),direction.x,direction.y,direction.z,vertices[offset],vertices[offset+1],vertices[offset+2],vertices[offset+5],vertices[offset+6],vertices[offset+7],vertices[offset+10],vertices[offset+11],vertices[offset+12],1e-6f);
                        if(distance>0&&distance<nearest){nearest=distance;found=offset;}
                    }
                    if(found<0)continue;
                    var hit=new JsonObject();hit.addProperty("tile",data.id);hit.addProperty("part",part);hit.addProperty("distance",nearest);var triangle=new JsonArray();
                    for(int vertex=0;vertex<3;vertex++){var point=new JsonArray();point.add(vertices[found+vertex*5]+data.anchorX);point.add(vertices[found+vertex*5+1]+data.anchorY);point.add(vertices[found+vertex*5+2]+data.anchorZ);triangle.add(point);}
                    hit.add("triangle",triangle);hits.add(hit);
                }
            }
            hits.sort(Comparator.comparingDouble(h->h.get("distance").getAsDouble()));var row=control.deepCopy();row.addProperty("liveFov",fov);
            row.add("cameraPosition",new Gson().toJsonTree(new double[]{eye.x,eye.y,eye.z}));row.add("direction",new Gson().toJsonTree(new float[]{direction.x,direction.y,direction.z}));
            if(control.has("blockSamples")&&control.get("blockSamples").getAsBoolean()){
                // Diagnostic only: locate visible vanilla filler independently
                // of the map mesh ray. Mesh occlusion must be assessed separately.
                for(double distance=0;distance<=160;distance+=.25){
                    var position=net.minecraft.core.BlockPos.containing(eye.x+direction.x*distance,eye.y+direction.y*distance,eye.z+direction.z*distance);
                    var state=mc.level.getBlockState(position);
                    if(state.isAir()||dev.realworldmc.EarthBlocks.isMapBlock(state)||state.getRenderShape()==net.minecraft.world.level.block.RenderShape.INVISIBLE)continue;
                    var block=new JsonObject();block.addProperty("distance",distance);block.addProperty("state",state.toString());
                    block.add("position",new Gson().toJsonTree(new int[]{position.getX(),position.getY(),position.getZ()}));
                    row.add("firstVisibleVanillaBlock",block);break;
                }
            }
            if(control.has("expectedTile")&&(hits.isEmpty()||hits.get(0).get("tile").getAsInt()!=control.get("expectedTile").getAsInt()||control.has("expectedPart")&&hits.get(0).get("part").getAsInt()!=control.get("expectedPart").getAsInt()))throw new AssertionError("Unexpected visible geometry at screen "+u+","+v+": "+(hits.isEmpty()?"none":hits.get(0)));
            if(control.has("expectedDistance")){
                double expected=control.get("expectedDistance").getAsDouble(),tolerance=control.get("distanceTolerance").getAsDouble();
                if(hits.isEmpty()||Math.abs(hits.get(0).get("distance").getAsDouble()-expected)>tolerance)throw new AssertionError("Unexpected first-hit distance at screen "+u+","+v+": "+(hits.isEmpty()?"none":hits.get(0)));
            }
            var nearest=new JsonArray();for(int i=0;i<Math.min(4,hits.size());i++)nearest.add(hits.get(i));row.add("hits",nearest);row.addProperty("qualification","Geometric ray; transparent texture texels are not rejected.");result.add(row);
        }
        return result;
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
                        // Ignore incidental canopy cards for wall controls, but
                        // include the explicitly requested vegetation part when
                        // the control measures a tree's actual trunk mesh.
                        boolean requestedPart=data.id==control.get("tile").getAsInt() && pi==control.get("part").getAsInt();
                        if ((!vegetation || requestedPart) && t>0 && t<distance) { distance=t; hit=data.id; part=pi; }
                    }
                }
            }
            if (hit!=control.get("tile").getAsInt() || part!=control.get("part").getAsInt() || Math.abs(distance-.6)>.025)
                throw new AssertionError("Inspection surface missing/obstructed at "+x+","+y+","+z+": "+hit+"/"+part+" distance "+distance);
            var row=control.deepCopy(); row.addProperty("hitTile",hit); row.addProperty("hitPart",part); row.addProperty("distance",distance);
            row.addProperty("firstHitTile",firstHit); row.addProperty("firstHitDistance",firstDistance);
            if (control.has("collider") && control.get("collider").getAsBoolean()) {
                var from=new net.minecraft.world.phys.Vec3(x+nx*1.6,y+ny*1.6,z+nz*1.6);
                var to=new net.minecraft.world.phys.Vec3(x-nx*.6,y-ny*.6,z-nz*.6);
                var collision=mc.level.clip(new net.minecraft.world.level.ClipContext(from,to,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
                if (collision.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK || !dev.realworldmc.EarthBlocks.isMapBlock(mc.level.getBlockState(collision.getBlockPos())))
                    throw new AssertionError("Inspection wall lacks native collision at "+x+","+y+","+z);
                row.addProperty("nativeCollider",collision.getBlockPos().toShortString());
            }
            results.add(row);
        }
        return results;
    }

    private static void writeReport(String status) throws Exception {
        var report = new JsonObject();
        report.addProperty("status",status);
        report.addProperty("rendererJar",Path.of(MapRenderer.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getFileName().toString());
        if(fractionalSupportChecks!=null)report.add("fractionalSupportChecks",fractionalSupportChecks);
        if(migrationChecks!=null)report.add("migrationChecks",migrationChecks);
        report.add("plan",plan);report.add("frames",frames);report.add("gravity",gravity);
        if(gravityFailureDetails!=null)report.add("gravityFailure",gravityFailureDetails);
        Files.writeString(Path.of("campus-"+plan.get("name").getAsString()+"-result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }

    private static void tickGravity(Minecraft mc, Map<?, ?> loaded, List<?> displayed) throws Exception {
        if(gravityFailure!=null){
            if(gravityFailureDetails!=null){
                String name="campus-"+plan.get("name").getAsString()+"-walking-failure.png";
                try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of(name));}
                gravityFailureDetails.addProperty("capture",name);
                gravityFailureDetails.addProperty("clientPosition",mc.player.position().toString());
            }
            writeReport("FAIL: native walking check: "+gravityFailure.getMessage());throw new AssertionError("Inspection native walking check failed",gravityFailure);
        }
        if(gravityIndex>gravityReportedIndex){
            if(plan.has("captureWalking")&&plan.get("captureWalking").getAsBoolean()){
                String name="campus-"+plan.get("name").getAsString()+"-walk-"+gravityReportedIndex+".png";
                try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of(name));}
                var row=gravity.get(gravityReportedIndex).getAsJsonObject();row.addProperty("capture",name);row.addProperty("clientPosition",mc.player.position().toString());
            }
            writeReport("RUNNING: native walking probes");gravityReportedIndex=gravityIndex;
        }
        var controls=plan.getAsJsonArray("gravityProbes");
        if(gravityIndex==controls.size()){
            if(plan.has("migration")){migrationChecks=CampusMigrationCheck.check(mc,plan.getAsJsonObject("migration"));if(migrationChecks==null)return;}
            writeReport("PASS: inspection cameras, surface controls and native gravity completed; visual assessment required");mc.stop();return;
        }
        var server=mc.getSingleplayerServer();var uuid=mc.player.getUUID();
        final int index=gravityIndex;
        var control=controls.get(index).getAsJsonObject();var target=control.getAsJsonArray("target");
        final double x=target.get(0).getAsDouble(),expected=target.get(1).getAsDouble(),z=target.get(2).getAsDouble();
        // A player spans 0.6 m, so a sloped surface may support its feet above
        // the centre-point sample. Optional supportHeight is independently
        // derived from exact triangle/footprint intersections in the frozen plan.
        // Centre render probing, landing tolerance and lateral checks remain.
        final double supportExpected=control.has("supportHeight")?control.get("supportHeight").getAsDouble():expected;
        if(!Double.isFinite(supportExpected)||supportExpected<expected-.0001||supportExpected>expected+.3)throw new IllegalArgumentException("Invalid footprint support height");
        final double supportTolerance=control.has("maxSupportError")?control.get("maxSupportError").getAsDouble():.51;
        if(!Double.isFinite(supportTolerance)||supportTolerance<=0||supportTolerance>.51)throw new IllegalArgumentException("Support tolerance may only tighten the default limit");
        final double drop=control.has("dropHeight")?control.get("dropHeight").getAsDouble():7;
        if(!Double.isFinite(drop)||drop<=0||drop>10)throw new IllegalArgumentException("Invalid gravity probe drop height");
        // Covered exterior spaces can have less than one block of headroom
        // above the standing player. Start within that space instead of
        // teleporting into its ceiling; the landing assertions stay identical.
        final double startY=control.has("startY")?control.get("startY").getAsDouble():expected+drop;
        if(!Double.isFinite(startY)||startY<expected-.51||startY>expected+10)throw new IllegalArgumentException("Invalid gravity probe start height");
        final String look=control.has("look")?" "+control.getAsJsonArray("look").get(0).getAsDouble()+" "+control.getAsJsonArray("look").get(1).getAsDouble():"";
        if(!gravityQueued){
            var one=new JsonArray();one.add(control);probe(mc,loaded,displayed,one);
            gravityQueued=true;gravityReady=false;gravityChecking=false;gravityReleased=false;gravityTicks=0;gravityAlignmentWaitTicks=0;
            server.execute(()->{try{
                var player=server.getPlayerList().getPlayer(uuid);player.setGameMode(net.minecraft.world.level.GameType.CREATIVE);
                // Hold the probe above the target while its chunks load and
                // collision alignment completes, then perform the actual drop.
                player.getAbilities().flying=true;player.onUpdateAbilities();
                server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s "+x+" "+startY+" "+z+look);
                gravityReady=true;
            }catch(Throwable error){gravityFailure=error;}});return;
        }
        if(!gravityReady||++gravityTicks<(gravityReleased?100:20)||gravityChecking)return;
        gravityChecking=true;
        server.execute(()->{try{
            var player=server.getPlayerList().getPlayer(uuid);
            if(!gravityReleased){
                var chunk=player.chunkPosition();
                if(!dev.realworldmc.CampusCollision.aligned(server.overworld(),chunk.x,chunk.z)){
                    if(gravityTicks>=1200){
                        var detail=new JsonObject();detail.addProperty("probe",index);detail.add("control",control.deepCopy());
                        detail.addProperty("serverPosition",player.position().toString());detail.addProperty("collisionAligned",false);
                        detail.addProperty("alignmentWaitTicks",gravityTicks);gravityFailureDetails=detail;
                        throw new AssertionError("Walking probe collision alignment timed out before release");
                    }
                    gravityChecking=false;return;
                }
                gravityAlignmentWaitTicks=gravityTicks;
                server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s "+x+" "+startY+" "+z+look);
                player.getAbilities().flying=false;player.onUpdateAbilities();
                gravityReleased=true;gravityTicks=0;gravityChecking=false;return;
            }
            double horizontalError=Math.hypot(player.getX()-x,player.getZ()-z);
            boolean freeBody=!control.has("requireBodyClearance")||!control.get("requireBodyClearance").getAsBoolean()||server.overworld().noCollision(player);
            if(!player.onGround()||Math.abs(player.getY()-supportExpected)>supportTolerance||horizontalError>.1||!freeBody){
                var detail=new JsonObject();detail.addProperty("probe",index);detail.add("control",control.deepCopy());
                detail.addProperty("serverPosition",player.position().toString());
                detail.addProperty("horizontalError",horizontalError);
                detail.addProperty("bodyClear",freeBody);detail.addProperty("supportExpectedY",supportExpected);
                detail.addProperty("velocity",player.getDeltaMovement().toString());
                detail.addProperty("onGround",player.onGround());detail.addProperty("flying",player.getAbilities().flying);
                var chunk=player.chunkPosition();detail.addProperty("collisionAligned",dev.realworldmc.CampusCollision.aligned(server.overworld(),chunk.x,chunk.z));
                var support=new JsonArray();var bounds=player.getBoundingBox();int floor=(int)Math.floor(player.getY());
                for(int bx=(int)Math.floor(bounds.minX);bx<=(int)Math.floor(bounds.maxX);bx++)
                for(int bz=(int)Math.floor(bounds.minZ);bz<=(int)Math.floor(bounds.maxZ);bz++)
                for(int by=floor-2;by<=floor;by++){
                    var pos=new net.minecraft.core.BlockPos(bx,by,bz);var row=new JsonObject();
                    row.addProperty("position",pos.toShortString());row.addProperty("state",server.overworld().getBlockState(pos).toString());support.add(row);
                }
                detail.add("supportBlocks",support);gravityFailureDetails=detail;
                throw new AssertionError("Probe "+index+" standing Y="+player.getY()+", mesh Y="+expected+", onGround="+player.onGround()+", horizontal error="+horizontalError);
            }
            var chunk=player.chunkPosition();
            if(!dev.realworldmc.CampusCollision.aligned(server.overworld(),chunk.x,chunk.z))throw new AssertionError("Walking probe chunk has not completed collision alignment");
            var row=control.deepCopy();row.addProperty("standingY",player.getY());row.addProperty("supportExpectedY",supportExpected);row.addProperty("onGround",player.onGround());row.addProperty("horizontalError",horizontalError);row.addProperty("bodyClear",freeBody);
            row.addProperty("alignmentWaitTicks",gravityAlignmentWaitTicks);
            if(control.has("requireFineWood")&&control.get("requireFineWood").getAsBoolean()){
                var profiles=new JsonArray();var level=server.overworld();
                for(int bx=(int)Math.floor(x)-2;bx<=(int)Math.floor(x)+2;bx++)
                for(int bz=(int)Math.floor(z)-2;bz<=(int)Math.floor(z)+2;bz++)
                for(int by=(int)Math.floor(expected)+1;by<=(int)Math.floor(expected)+3;by++){
                    var pos=new net.minecraft.core.BlockPos(bx,by,bz);var state=level.getBlockState(pos);
                    if(!(state.getBlock() instanceof dev.realworldmc.CampusWoodBlock))continue;
                    var saved=net.minecraft.nbt.NbtUtils.writeBlockState(state);
                    var restored=net.minecraft.nbt.NbtUtils.readBlockState(server.registryAccess().lookupOrThrow(net.minecraft.core.registries.Registries.BLOCK),saved);
                    if(restored!=state)throw new AssertionError("Fine wood state did not survive NBT round trip");
                    var shape=state.getCollisionShape(level,pos).bounds();var entry=new JsonObject();
                    entry.addProperty("position",pos.toShortString());entry.addProperty("profile",dev.realworldmc.CampusWoodBlock.profile(state));
                    var bounds=new JsonArray();for(double value:new double[]{shape.minX,shape.minY,shape.minZ,shape.maxX,shape.maxY,shape.maxZ})bounds.add(value);
                    entry.add("bounds",bounds);profiles.add(entry);
                }
                if(profiles.isEmpty())throw new AssertionError("No fine wood proxies beside retained collision regression point");
                row.add("fineWoodProfiles",profiles);row.addProperty("woodProfileNbtRoundTrip",true);
            }
            if(control.has("requireFineSolid")&&control.get("requireFineSolid").getAsBoolean()){
                var profiles=new JsonArray();var level=server.overworld();
                for(int bx=(int)Math.floor(x)-2;bx<=(int)Math.floor(x)+2;bx++)
                for(int bz=(int)Math.floor(z)-2;bz<=(int)Math.floor(z)+2;bz++)
                for(int by=(int)Math.floor(expected)+1;by<=(int)Math.floor(expected)+3;by++){
                    var pos=new net.minecraft.core.BlockPos(bx,by,bz);var state=level.getBlockState(pos);
                    if(!(state.getBlock() instanceof dev.realworldmc.CampusSolidBlock solid))continue;
                    var saved=net.minecraft.nbt.NbtUtils.writeBlockState(state);
                    var restored=net.minecraft.nbt.NbtUtils.readBlockState(server.registryAccess().lookupOrThrow(net.minecraft.core.registries.Registries.BLOCK),saved);
                    if(restored!=state)throw new AssertionError("Fine solid state did not survive NBT round trip");
                    if(!state.is(net.minecraft.tags.BlockTags.MINEABLE_WITH_PICKAXE))throw new AssertionError("Fine solid lost pickaxe tag");
                    var expectedCut=solid.material==4?net.minecraft.world.level.block.Blocks.STONE:net.minecraft.world.level.block.Blocks.WHITE_TERRACOTTA;
                    if(!dev.realworldmc.EarthBlocks.cutMaterial(state).is(expectedCut))throw new AssertionError("Fine solid cut material changed");
                    var shape=state.getCollisionShape(level,pos).bounds();var entry=new JsonObject();
                    entry.addProperty("position",pos.toShortString());entry.addProperty("material",solid.material);entry.addProperty("profile",dev.realworldmc.CampusSolidBlock.profile(state));
                    var bounds=new JsonArray();for(double value:new double[]{shape.minX,shape.minY,shape.minZ,shape.maxX,shape.maxY,shape.maxZ})bounds.add(value);
                    entry.add("bounds",bounds);profiles.add(entry);
                }
                if(profiles.isEmpty())throw new AssertionError("No fine solids beside retained collision regression point");
                row.add("fineSolidProfiles",profiles);row.addProperty("solidProfileNbtRoundTrip",true);row.addProperty("solidMaterialChecks",true);
            }
            gravity.add(row);
            gravityIndex++;gravityQueued=false;
        }catch(Throwable error){gravityFailure=error;}});
    }

    public static void tick(Minecraft mc) throws Exception {
        // Called only while the parent reports full streaming/upload readiness.
        // Wait again at each position rather than using the prior camera's state.
        var cameras = cameras();
        if(fractionalSupportChecks==null&&plan.has("checkFractionalSupports")&&plan.get("checkFractionalSupports").getAsBoolean())fractionalSupportChecks=CampusFractionalSupportChecks.verify(mc);
        if(ticks==0&&phase<cameras.size()){
            var view=cameras.get(phase).getAsJsonObject();
            if(view.has("guiScale")){
                int scale=view.get("guiScale").getAsInt();
                if(scale<0||scale>8)throw new AssertionError("Invalid inspection GUI scale");
                mc.options.guiScale().set(scale);
                mc.resizeDisplay();
            }
            if(view.has("reflections"))CampusReflections.enabled=view.get("reflections").getAsBoolean();
            if(view.has("worldTime")){
                long time=view.get("worldTime").getAsLong();
                if(time<0||time>=24000)throw new AssertionError("Inspection time must be in one Minecraft day");
                mc.player.connection.sendCommand("time set "+time);
            }
        }
        if (++ticks < 200) return;
        var loadedField = MapRenderer.class.getDeclaredField("loaded");
        var displayedField = MapRenderer.class.getDeclaredField("displayed");
        loadedField.setAccessible(true); displayedField.setAccessible(true);
        var loaded = (Map<?, ?>) loadedField.get(MapRenderer.INSTANCE);
        var displayed = (List<?>) displayedField.get(MapRenderer.INSTANCE);
        if(phase==cameras.size()){tickGravity(mc,loaded,displayed);return;}
        if(plan.has("migration")&&migrationChecks==null){migrationChecks=CampusMigrationCheck.check(mc,plan.getAsJsonObject("migration"));if(migrationChecks==null)return;}
        var camera = cameras.get(phase).getAsJsonObject();
        var ids = new JsonArray(); long triangles = 0;
        for (var id : displayed) {
            ids.add((Integer) id);
            for (var part : ((MapTile) loaded.get(id)).data.parts) triangles += part.triangleCount();
        }
        String name = "campus-" + plan.get("name").getAsString() + "-" + phase + ".png";
        recordSourceTriangles(loaded,displayed,name.substring(0,name.length()-4));
        try (var image = Screenshot.takeScreenshot(mc.getMainRenderTarget())) { image.writeToFile(Path.of(name)); }
        var row = camera.deepCopy();
        if(camera.has("materialControls"))row.add("gpuMaterialControls",CampusMaterialMaskCheck.check(mc,camera.getAsJsonObject("materialControls")));
        row.addProperty("capture", name); row.addProperty("playerPosition", mc.player.position().toString());
        row.addProperty("triangles", triangles); row.add("displayedIds", ids);
        row.addProperty("fps",mc.getFps());
        row.addProperty("actualGuiScale",mc.getWindow().getGuiScale());
        row.addProperty("guiWidth",mc.getWindow().getGuiScaledWidth());
        row.addProperty("guiHeight",mc.getWindow().getGuiScaledHeight());
        long worldTime=Math.floorMod(mc.level.getDayTime(),24000L);
        row.addProperty("worldTime",worldTime);
        if(camera.has("worldTime")&&worldTime!=camera.get("worldTime").getAsLong())
            throw new AssertionError("Inspection time did not settle at requested value");
        if(plan.has("reflectionEvidence")&&plan.get("reflectionEvidence").getAsBoolean()){
            var shaderField=MapRenderer.class.getDeclaredField("campusGroundShader");shaderField.setAccessible(true);
            var shader=(net.minecraft.client.renderer.ShaderInstance)shaderField.get(null);
            float strength=org.lwjgl.opengl.GL20.glGetUniformf(shader.getId(),org.lwjgl.opengl.GL20.glGetUniformLocation(shader.getId(),"PlanarStrength"));
            var reflection=new JsonObject();reflection.addProperty("strength",strength);reflection.addProperty("updates",CampusReflections.updates);reflection.addProperty("stateChecks",CampusReflections.stateChecks);
            if(strength>0){
                if(CampusReflections.selected==null||CampusReflections.stateChecks!=CampusReflections.updates)throw new AssertionError("Unverified inspection reflection pass");
                reflection.addProperty("drawCalls",CampusReflections.draws);reflection.addProperty("cpuMilliseconds",CampusReflections.lastMilliseconds);
                int location=org.lwjgl.opengl.GL20.glGetUniformLocation(shader.getId(),"PlanarBaseWeight");
                if(location>=0){
                    float weight=org.lwjgl.opengl.GL20.glGetUniformf(shader.getId(),location);reflection.addProperty("baseWeight",weight);
                    if(camera.has("reflectionBaseWeight")&&Math.abs(weight-camera.get("reflectionBaseWeight").getAsFloat())>.0001)throw new AssertionError("Unexpected reflection material weight");
                }else if(camera.has("reflectionBaseWeight"))throw new AssertionError("Reflection material weight uniform missing");
                reflection.addProperty("planeTile",CampusReflections.selected.tile);
                var plane=CampusReflections.selected.equation;
                reflection.add("plane",new Gson().toJsonTree(new float[]{plane.x,plane.y,plane.z,plane.w}));
                var bounds=CampusReflections.selected.bounds;
                reflection.add("bounds",new Gson().toJsonTree(new double[]{bounds.minX,bounds.minY,bounds.minZ,bounds.maxX,bounds.maxY,bounds.maxZ}));
                String capture="campus-"+plan.get("name").getAsString()+"-reflection-"+phase+".png";CampusReflections.capture(Path.of(capture));reflection.addProperty("capture",capture);
            }
            if(camera.has("reflections")&&!camera.get("reflections").getAsBoolean()&&strength!=0)throw new AssertionError("Disabled reflection still active");
            if(camera.has("reflectionTile")&&(strength!=1||CampusReflections.selected==null||CampusReflections.selected.tile!=camera.get("reflectionTile").getAsInt()))throw new AssertionError("Expected reconstructed glazing has no verified reflection");
            if(camera.has("reflectionPoint")){
                var point=camera.getAsJsonArray("reflectionPoint");
                if(strength!=1||CampusReflections.selected==null||Math.abs(CampusReflections.selected.equation.dot(new org.joml.Vector4f(point.get(0).getAsFloat(),point.get(1).getAsFloat(),point.get(2).getAsFloat(),1)))>.03)throw new AssertionError("Reflection selected a different pane from the visible glass control");
            }
            row.add("reflection",reflection);
        }
        try {
            if(camera.has("screenRays"))row.add("screenRays",screenRays(mc,loaded,displayed,camera.getAsJsonArray("screenRays")));
            if(camera.has("probes"))row.add("probes",probe(mc,loaded,displayed,camera.getAsJsonArray("probes")));
        } catch (AssertionError failure) {
            row.addProperty("geometryFailure",failure.getMessage());frames.add(row);
            writeReport("FAIL: inspection geometry control");
            throw failure;
        }
        boolean missingWater=false,blockedWater=false;
        if(camera.has("waterColumns")){
            var columns=new JsonArray();
            for(var item:camera.getAsJsonArray("waterColumns")){
                var control=item.getAsJsonObject();int x=control.get("x").getAsInt(),z=control.get("z").getAsInt();
                var heights=new JsonArray();
                for(int y=40;y<=100;y++){
                    var state=mc.level.getBlockState(new net.minecraft.core.BlockPos(x,y,z));
                    if(state.getFluidState().is(net.minecraft.tags.FluidTags.WATER))heights.add(y);
                }
                var column=control.deepCopy();column.add("waterBlockY",heights);columns.add(column);
                if(heights.isEmpty())missingWater=true;
                int clearance=camera.has("waterClearanceBlocks")?camera.get("waterClearanceBlocks").getAsInt():0;
                if(clearance<0||clearance>4)throw new IllegalArgumentException("Invalid water clearance check");
                if(!heights.isEmpty()&&clearance>0){
                    int top=heights.get(heights.size()-1).getAsInt();var above=new JsonArray();
                    for(int y=top+1;y<=top+clearance;y++){
                        var state=mc.level.getBlockState(new net.minecraft.core.BlockPos(x,y,z));
                        var cell=new JsonObject();cell.addProperty("y",y);cell.addProperty("state",state.toString());above.add(cell);
                        if(!state.isAir())blockedWater=true;
                    }
                    column.add("clearanceStates",above);
                }
            }
            row.add("waterColumns",columns);row.addProperty("waterColumnsPass",!missingWater);row.addProperty("waterClearancePass",!blockedWater);
        }
        frames.add(row);
        if(missingWater){writeReport("FAIL: mapped river columns contain no native water");throw new AssertionError("Mapped river columns contain no native water; inspect captured column heights and image");}
        if(blockedWater){writeReport("FAIL: river clearance contains solid source or reconstructed blocks");throw new AssertionError("River clearance blocked; inspect captured native states");}
        boolean needsGravity=plan.has("gravityProbes")&&!plan.getAsJsonArray("gravityProbes").isEmpty();
        writeReport(phase==cameras.size()-1&&!needsGravity?"PASS: inspection cameras captured; visual assessment required":"RUNNING");
        if (++phase == cameras.size()) { if(!needsGravity)mc.stop();return; }
        ticks = 0; String next = cameras.get(phase).getAsJsonObject().get("position").getAsString();
        var uuid = mc.player.getUUID();
        mc.getSingleplayerServer().execute(() -> {
            var player = mc.getSingleplayerServer().getPlayerList().getPlayer(uuid);
            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4), "tp @s " + next);
        });
    }
}
