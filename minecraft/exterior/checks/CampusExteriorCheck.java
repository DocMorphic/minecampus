package dev.realworldmc.client;

import dev.realworldmc.EarthConfig;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.world.level.GameType;
import java.nio.file.Files;
import java.nio.file.Path;

/** Hidden, isolated native-client captures; not included in the distributed datapack. */
public final class CampusExteriorCheck implements ClientModInitializer {
    private static final String WORLD=System.getProperty("minecampus.checkWorld","campus-check");
    private boolean opened, moved, walkingStarted;
    private volatile boolean gameplayVerified, terraceVerified, frontageVerified;
    private volatile boolean frontageQueued;
    private boolean terraceStarted, terraceCheckQueued;
    private int terraceTicks;
    private boolean roofStarted, roofCheckQueued;
    private volatile boolean roofVerified;
    private int roofTicks;
    private int ticks, stage=Boolean.getBoolean("minecampus.inspectOnly")?Integer.getInteger("minecampus.inspectStage",3):0, total, readyTicks;
    private volatile Throwable failure;
    private volatile int expectedJournal;
    private volatile boolean collisionVerified;
    private volatile boolean collisionProofQueued;
    private static final String[] NAMES = {"campus-final-ground.png", "campus-final-aerial.png", "campus-tnt.png", "campus-route-west.png", "campus-route-south.png", "campus-route-north.png", "campus-source-check.png", "campus-ias.png", "campus-photo-north.png", "campus-former-mensa.png", "campus-mensa-terrace.png"};
    private static final String[] CAMERAS = {
        "39.961711 65.797294 -62.90048 -103.360657 4.800037",
        "-60 120 120 -153.435 20.44",
        "38 73 -59 -135 50",
        "35 65 -40 90 0",
        "35 65 100 180 0",
        "50 65 -190 0 0",
        "150 65 -220 -90 0",
        "65 65 -157 -166 -8",
        "205 65 -238 0 0",
        "0 64.25 -216 180 -5",
        "0 68 -238 180 0"
    };

    @Override public void onInitializeClient() {
        ClientLifecycleEvents.CLIENT_STARTED.register(mc -> {
            org.lwjgl.glfw.GLFW.glfwHideWindow(mc.getWindow().getWindow());
            if(!Path.of("").toAbsolutePath().getFileName().toString().equals("run-campus-check"))throw new AssertionError("QA must run only in its isolated directory");
            if(!WORLD.matches("campus-check(-[a-z0-9]+)*"))throw new AssertionError("QA save must have an explicit campus-check name");
            EarthConfig.get().setupComplete = true;
            EarthConfig.get().autoSpaceFlight = false;
            mc.options.pauseOnLostFocus = false;
            mc.options.renderDistance().set(10);
            mc.options.simulationDistance().set(5);
            mc.options.hideGui = true;
            mc.options.cloudStatus().set(net.minecraft.client.CloudStatus.OFF);
            mc.options.getSoundSourceOptionInstance(net.minecraft.sounds.SoundSource.MASTER).set(0.0);
        });
        ClientTickEvents.END_CLIENT_TICK.register(this::tick);
    }

    private void tick(Minecraft mc) {
        try {
            if (++total > 9000) throw new AssertionError("Native campus client capture timed out");
            if (failure != null) throw new AssertionError("Integrated server check failed", failure);
            if (!opened && mc.getOverlay()==null) {
                opened=true;
                mc.createWorldOpenFlows().openWorld(WORLD, () -> fail(mc, new AssertionError("QA save did not open")));
            }
            if (mc.screen instanceof net.minecraft.client.gui.screens.ConfirmScreen
                || mc.screen instanceof net.minecraft.client.gui.screens.BackupConfirmScreen) {
                for (var child : mc.screen.children()) if (child instanceof net.minecraft.client.gui.components.Button button) {
                    String label = button.getMessage().getString();
                    if (label.equals("Proceed") || label.equals("Yes") || label.equals("I know what I'm doing!")
                        || button.getMessage().getContents() instanceof net.minecraft.network.chat.contents.TranslatableContents text
                        && text.getKey().equals("selectWorld.backupJoinSkipButton")) {
                        button.onPress(); return;
                    }
                }
            }
            if (mc.player==null || mc.getSingleplayerServer()==null || mc.getOverlay()!=null) return;
            if(stage==NAMES.length){
                if(!walkingStarted){
                    walkingStarted=true;ticks=0;
                    mc.getSingleplayerServer().execute(()->{
                        try{
                            var world=mc.getSingleplayerServer().overworld();var history=dev.realworldmc.MapEdits.storage(world);
                            var block=new net.minecraft.core.BlockPos(44,64,-63);
                            if(history.original.isEmpty()||!world.getBlockState(block).isAir())throw new AssertionError("TNT did not excavate surveyed terrain");
                            var snapshot=new java.util.HashMap<>(history.original);
                            var guard=dev.realworldmc.CampusCollision.class.getDeclaredField("updating");guard.setAccessible(true);var applying=(ThreadLocal<Boolean>)guard.get(null);applying.set(true);
                            try{for(var e:snapshot.entrySet())world.setBlock(net.minecraft.core.BlockPos.of(e.getKey()),e.getValue(),18);}finally{applying.set(false);}
                            history.original.clear();history.setDirty();
                            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s 40.5 78 -63.5");
                            for(var participant:world.players())dev.realworldmc.MapEdits.snapshot(participant);
                        }catch(Throwable error){failure=error;}
                    });
                    return;
                }
                if(++ticks<100)return;
                if(!gameplayVerified){
                    mc.getSingleplayerServer().execute(()->{
                        try{
                            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                            if(!player.onGround()||Math.abs(player.getY()-65)>.51)throw new AssertionError("Walking collider does not match survey ground: "+player.getY());
                            Files.writeString(Path.of("campus-gameplay-result.txt"),"PASS: native TNT excavated surveyed mesh; restoration succeeded; player landed on surveyed ground at Y="+player.getY());
                            gameplayVerified=true;
                        }catch(Throwable error){failure=error;}
                    });
                    return;
                }
                if(!terraceStarted){
                    terraceStarted=true;
                    mc.getSingleplayerServer().execute(()->{
                        var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                        mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s 72.5 74 -200.5");
                    });
                    return;
                }
                if(++terraceTicks<120)return;
                if(!terraceVerified){
                    if(!terraceCheckQueued){
                        terraceCheckQueued=true;
                        mc.getSingleplayerServer().execute(()->{
                            try{
                                var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                                if(!player.onGround()||Math.abs(player.getY()-67)>.51)throw new AssertionError("IAS terrace collider mismatch: "+player.getY());
                                Files.writeString(Path.of("campus-terrace-result.txt"),"PASS: native gravity landed player on reconstructed IAS terrace at Y="+player.getY());
                                terraceVerified=true;
                            }catch(Throwable error){failure=error;}
                        });
                    }
                    return;
                }
                if(Boolean.getBoolean("minecampus.requirePhotographicFacade")) {
                    if(!roofStarted){
                        roofStarted=true;
                        mc.getSingleplayerServer().execute(()->{
                            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s 205.5 85 -203.5");
                        });
                        return;
                    }
                    if(++roofTicks<120)return;
                    if(!roofVerified){
                        if(!roofCheckQueued){
                            roofCheckQueued=true;
                            mc.getSingleplayerServer().execute(()->{
                                try{
                                    var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                                    // Surveyed roof at this X/Z is Y=72.264896.
                                    // Native proxy blocks should match within half a block.
                                    if(!player.onGround()||Math.abs(player.getY()-72.264896)>.51)throw new AssertionError("Photographic building roof collider mismatch: "+player.getY());
                                    Files.writeString(Path.of("campus-roof-result.txt"),"PASS: native gravity landed player on survey roof supporting the photographic facade at Y="+player.getY());
                                    roofVerified=true;
                                }catch(Throwable error){failure=error;}
                            });
                        }
                        return;
                    }
                }
                Files.writeString(Path.of("campus-client-result.txt"),"PASS: eleven ground, aerial, TNT, promenade, source-limit, IAS, photographic facade and former Mensa frames captured after full streaming readiness");mc.stop();return;
            }
            if (!moved) {
                moved=true; ticks=0; readyTicks=0; mc.setScreen(null);
                var server=mc.getSingleplayerServer(); var playerId=mc.player.getUUID();
                String camera=CAMERAS[stage];
                server.execute(() -> {
                    try {
                        var player=server.getPlayerList().getPlayer(playerId);
                        player.setGameMode(GameType.SPECTATOR);
                        var source=player.createCommandSourceStack().withPermission(4);
                        server.getCommands().performPrefixedCommand(source, "execute in minecraft:overworld run tp @s " + camera);
                        server.getCommands().performPrefixedCommand(source, "time set noon");
                        server.getCommands().performPrefixedCommand(source, "gamerule doMobSpawning false");
                        server.getCommands().performPrefixedCommand(source, "gamerule doMobLoot false");
                        server.getCommands().performPrefixedCommand(source, "kill @e[type=!minecraft:player]");
                        server.getCommands().performPrefixedCommand(source, "weather clear");
                        if(stage==2){
                            var world=server.overworld();var target=new net.minecraft.core.BlockPos(44,64,-63);
                            if(!dev.realworldmc.EarthBlocks.isMapBlock(world.getBlockState(target)))throw new AssertionError("TNT target is not surveyed collision terrain");
                            var tnt=new net.minecraft.world.entity.item.PrimedTnt(world,44.5,67,-62.5,player);tnt.setFuse(30);world.addFreshEntity(tnt);
                        }
                        if(stage==0){
                            var world=server.overworld();
                            if(Boolean.getBoolean("minecampus.pristineCheck")) {
                                var edits=dev.realworldmc.MapEdits.storage(world);var saved=new java.util.HashMap<>(edits.original);
                                var guard=dev.realworldmc.CampusCollision.class.getDeclaredField("updating");guard.setAccessible(true);var applying=(ThreadLocal<Boolean>)guard.get(null);applying.set(true);
                                try{for(var entry:saved.entrySet())world.setBlock(net.minecraft.core.BlockPos.of(entry.getKey()),entry.getValue(),18);}finally{applying.set(false);}
                                edits.original.clear();edits.setDirty();
                                var method=dev.realworldmc.CampusCollision.class.getDeclaredMethod("storage",net.minecraft.server.level.ServerLevel.class);method.setAccessible(true);
                                var data=(net.minecraft.world.level.saveddata.SavedData)method.invoke(null,world);var done=data.getClass().getDeclaredField("done");done.setAccessible(true);((java.util.Set<Long>)done.get(data)).clear();data.setDirty();
                                for(var participant:world.players())dev.realworldmc.MapEdits.snapshot(participant);
                            }
                            var block=new net.minecraft.core.BlockPos(33,64,-92);var mined=new net.minecraft.core.BlockPos(34,64,-92);
                            world.setBlock(block,net.minecraft.world.level.block.Blocks.DIAMOND_BLOCK.defaultBlockState(),2);
                            world.getChunkAt(mined).setBlockState(mined,dev.realworldmc.EarthBlocks.MAP_DIRT.defaultBlockState(),false);
                            world.setBlock(mined,net.minecraft.world.level.block.Blocks.AIR.defaultBlockState(),2);
                            dev.realworldmc.MapEdits.storage(world).record(mined,dev.realworldmc.EarthBlocks.MAP_DIRT.defaultBlockState());
                            if(!dev.realworldmc.MapEdits.storage(world).original.containsKey(mined.asLong()))throw new AssertionError("Excavation fixture was not recorded");
                            expectedJournal=dev.realworldmc.MapEdits.storage(world).original.size();
                            var method=dev.realworldmc.CampusCollision.class.getDeclaredMethod("storage",net.minecraft.server.level.ServerLevel.class);method.setAccessible(true);
                            var data=(net.minecraft.world.level.saveddata.SavedData)method.invoke(null,world);var field=data.getClass().getDeclaredField("done");field.setAccessible(true);
                            ((java.util.Set<Long>)field.get(data)).remove(net.minecraft.world.level.ChunkPos.asLong(2,-6));data.setDirty();
                        }
                    } catch (Throwable error) { failure=error; }
                });
                return;
            }
            if (++ticks % 200 == 0) {
                var data = new com.google.gson.JsonObject();
                var renderer = MapRenderer.INSTANCE;
                for (String name : new String[]{"wanted", "displayed", "loaded", "loading", "uploadQueue"}) {
                    var f=MapRenderer.class.getDeclaredField(name); f.setAccessible(true); Object value=f.get(renderer);
                    int count=value instanceof java.util.Map<?,?> m ? m.size() : ((java.util.Collection<?>)value).size();
                    data.addProperty(name,count);
                }
                var f=MapRenderer.class.getDeclaredField("loaded");f.setAccessible(true);
                var d=MapRenderer.class.getDeclaredField("displayed");d.setAccessible(true);
                var loaded=(java.util.Map<Integer,MapTile>)f.get(renderer);
                var shown=(java.util.List<Integer>)d.get(renderer);
                long triangles=0;int fine=0;var ids=new com.google.gson.JsonArray();
                for(int id:shown){ids.add(id);var t=loaded.get(id);if(t!=null){if(t.data.fine)fine++;for(var part:t.data.parts)triangles+=part.triangleCount();}}
                data.addProperty("fps",mc.getFps());data.addProperty("camera",CAMERAS[stage]);data.addProperty("fineDisplayed",fine);data.addProperty("triangles",triangles);data.add("displayedIds",ids);
                Files.writeString(Path.of("campus-metrics-"+stage+"-"+ticks+".json"),data.toString());
            }
            var renderer=MapRenderer.INSTANCE;
            var wf=MapRenderer.class.getDeclaredField("wanted");wf.setAccessible(true);
            var lf=MapRenderer.class.getDeclaredField("loaded");lf.setAccessible(true);
            var df=MapRenderer.class.getDeclaredField("displayed");df.setAccessible(true);
            var want=(java.util.List<?>)wf.get(renderer);var loaded=(java.util.Map<?,?>)lf.get(renderer);
            boolean ready=!want.isEmpty()&&renderer.pendingTileSelection==0;
            for(Object w:want){var id=w.getClass().getDeclaredField("id");id.setAccessible(true);if(!loaded.containsKey(id.getInt(w)))ready=false;}
            if(((java.util.List<?>)df.get(renderer)).size()!=want.size())ready=false;
            readyTicks=ready?readyTicks+1:0;
            if(ticks<200 || readyTicks<40)return;
            if(stage==10&&Boolean.getBoolean("minecampus.requireMensaFront")&&!((java.util.List<?>)df.get(renderer)).contains(1_000_030_005))throw new AssertionError("Former Mensa structural frontage was not displayed");
            if(stage==9&&Boolean.getBoolean("minecampus.requireVisibleFacade")&&!((java.util.List<?>)df.get(renderer)).contains(1_000_050_038))throw new AssertionError("Visible former Mensa facade was not accepted/displayed");
            if(stage==6&&Boolean.getBoolean("minecampus.requirePhotographicFacade")&&!((java.util.List<?>)df.get(renderer)).contains(1_000_050_000))throw new AssertionError("Photographic facade was not accepted/displayed");
            if(stage==10&&Boolean.getBoolean("minecampus.requireMensaFront")&&!Boolean.getBoolean("minecampus.inspectOnly")&&!frontageVerified){
                if(!frontageQueued){frontageQueued=true;mc.getSingleplayerServer().execute(()->{
                    try{
                        var world=mc.getSingleplayerServer().overworld();
                        if(!dev.realworldmc.CampusCollision.aligned(world,0,-16)){frontageQueued=false;return;}
                        if(!world.getBlockState(new net.minecraft.core.BlockPos(5,68,-247)).isAir())throw new AssertionError("Old flat collision wall still blocks the Mensa glazing recess");
                        if(!dev.realworldmc.EarthBlocks.isMapBlock(world.getBlockState(new net.minecraft.core.BlockPos(5,68,-249))))throw new AssertionError("Recessed Mensa glazing has no collision");
                        if(!dev.realworldmc.EarthBlocks.isMapBlock(world.getBlockState(new net.minecraft.core.BlockPos(5,70,-247))))throw new AssertionError("Mensa canopy beam has no collision");
                        Files.writeString(Path.of("campus-frontage-result.txt"),"PASS: former flat facade is open at (5,68,-247); recessed glazing and overhead canopy retain collision");frontageVerified=true;
                    }catch(Throwable error){failure=error;}
                });}
                return;
            }
            if(stage==0&&!collisionVerified){
                if(!collisionProofQueued){
                    collisionProofQueued=true;
                    mc.getSingleplayerServer().execute(()->{
                        try{
                            var world=mc.getSingleplayerServer().overworld();
                            if(!dev.realworldmc.CampusCollision.aligned(world,2,-6)){collisionProofQueued=false;return;}
                            if(!world.getBlockState(new net.minecraft.core.BlockPos(33,64,-92)).is(net.minecraft.world.level.block.Blocks.DIAMOND_BLOCK))throw new AssertionError("Player build overwritten during collision migration");
                            if(!world.getBlockState(new net.minecraft.core.BlockPos(34,64,-92)).isAir())throw new AssertionError("Recorded excavation changed during collision migration: "+world.getBlockState(new net.minecraft.core.BlockPos(34,64,-92)));
                            if(dev.realworldmc.MapEdits.storage(world).original.size()!=expectedJournal)throw new AssertionError("Terrain alignment was incorrectly recorded as player damage");
                            Files.writeString(Path.of("campus-collision-result.txt"),"PASS: player block and recorded excavation preserved; migration created no damage records; changed proxies="+dev.realworldmc.CampusCollision.changedBlocks);
                            // Remove only this test's fixtures after verifying their survival.
                            String q="/campus/collision?"+dev.realworldmc.ServiceClient.originQuery(48.265,11.671,519.7618173672081)+"&cx=2&cz=-6&minY=48&height=96";
                            byte[] patch=dev.realworldmc.ServiceClient.getBytes(q,java.time.Duration.ofSeconds(30));
                            for(int x:new int[]{33,34}){
                                var pos=new net.minecraft.core.BlockPos(x,64,-92);int code=patch[((64-48)*16+(-92&15))*16+(x&15)]&255;
                                if(code==255)throw new AssertionError("Fixture position outside collision patch");
                                world.setBlock(pos,dev.realworldmc.EarthBlocks.byCode(code),18);dev.realworldmc.MapEdits.storage(world).original.remove(pos.asLong());
                            }
                            dev.realworldmc.MapEdits.storage(world).setDirty();for(var participant:world.players())dev.realworldmc.MapEdits.snapshot(participant);
                            collisionVerified=true;
                        }catch(Throwable error){failure=error;}
                    });
                }
                return;
            }
            if(stage==0||stage==3||stage==5||stage==6||stage==9||stage==10){
                var picks=new com.google.gson.JsonArray();
                var camera=mc.gameRenderer.getMainCamera();
                var fovMethod=net.minecraft.client.renderer.GameRenderer.class.getDeclaredMethod("getFov",net.minecraft.client.Camera.class,float.class,boolean.class);fovMethod.setAccessible(true);
                double actualFov=((Number)fovMethod.invoke(mc.gameRenderer,camera,1.0f,true)).doubleValue();
                float tanHalf=(float)Math.tan(Math.toRadians(actualFov)*.5);
                float[][] pixelsToPick=new float[][]{{.81f,.435f},{.38f,.443f}};
                if(stage==6)pixelsToPick=new float[][]{{.75f,.46f},{.8f,.5f},{.9f,.45f},{.38f,.38f},{.37f,.43f},{.766f,.55f}};
                if(stage==10)pixelsToPick=new float[][]{{.15f,.55f},{.5f,.55f},{.85f,.55f}};
                if(stage==9)pixelsToPick=new float[][]{{.78f,.35f},{.84f,.43f},{.96f,.40f},{.265f,.58f},{.51f,.59f},{.65f,.48f},{.745f,.615f},{.1f,.6f},{.18f,.55f},{.35f,.58f},{.58f,.56f},{.7f,.55f},{.82f,.41f}};
                if(stage==3||stage==5){
                    try(var frameImage=Screenshot.takeScreenshot(mc.getMainRenderTarget())){
                        var candidates=new java.util.ArrayList<int[]>();int width=frameImage.getWidth(),height=frameImage.getHeight();long sumX=0,sumY=0;
                        for(int y=(int)(height*(stage==3?.14:.01));y<(int)(height*(stage==3?.25:.15));y+=2)for(int x=(int)(width*(stage==3?.85:.70));x<(int)(width*(stage==3?.92:.82));x+=2){
                            int rgba=frameImage.getPixelRGBA(x,y),red=rgba&255,green=(rgba>>>8)&255,blue=(rgba>>>16)&255;
                            if(stage==3?(red>100&&red>green*.9&&red>blue*.85):(red<90&&green<100&&blue<110)){candidates.add(new int[]{x,y});sumX+=x;sumY+=y;}
                        }
                        if(!candidates.isEmpty()){
                            double cx=(double)sumX/candidates.size(),cy=(double)sumY/candidates.size();int[] best=candidates.get(0);double distance=Double.POSITIVE_INFINITY;
                            for(var point:candidates){double d=Math.pow(point[0]-cx,2)+Math.pow(point[1]-cy,2);if(d<distance){distance=d;best=point;}}
                            pixelsToPick=new float[][]{{(best[0]+.5f)/width,(best[1]+.5f)/height}};
                        }
                    }
                }
                for(float[] pixel:pixelsToPick){
                    var forward=new org.joml.Vector3f(camera.getLookVector());
                    var right=new org.joml.Vector3f(forward).cross(0,1,0).normalize();
                    var up=new org.joml.Vector3f(right).cross(forward).normalize();
                    var ray=new org.joml.Vector3f(forward).add(right.mul((pixel[0]*2-1)*tanHalf*16/9)).add(up.mul((1-pixel[1]*2)*tanHalf)).normalize();
                    var eye=camera.getPosition();float nearest=10000;int hit=-1;
                    for(var item:loaded.values()){
                        var tile=(MapTile)item;var data=tile.data;
                        if(!((java.util.List<?>)df.get(renderer)).contains(data.id))continue;
                        for(var part:data.parts){var v=part.vertices;
                            for(int o=0;o<v.length;o+=15){
                                float t=org.joml.Intersectionf.intersectRayTriangle((float)(eye.x-data.anchorX),(float)(eye.y-data.anchorY),(float)(eye.z-data.anchorZ),ray.x,ray.y,ray.z,v[o],v[o+1],v[o+2],v[o+5],v[o+6],v[o+7],v[o+10],v[o+11],v[o+12],1e-6f);
                                if(t>0&&t<nearest){nearest=t;hit=data.id;}
                            }
                        }
                    }
                    var pick=new com.google.gson.JsonObject();var region=dev.realworldmc.EarthRegions.at((int)Math.floor(eye.x),(int)Math.floor(eye.z));if(region!=null)pick.addProperty("frameGroundHeight",region.groundHeight());pick.addProperty("u",pixel[0]);pick.addProperty("v",pixel[1]);pick.addProperty("fov",actualFov);pick.addProperty("tile",hit);pick.addProperty("x",eye.x+ray.x*nearest);pick.addProperty("y",eye.y+ray.y*nearest);pick.addProperty("z",eye.z+ray.z*nearest);var blockHit=mc.level.clip(new net.minecraft.world.level.ClipContext(eye,eye.add(ray.x*256,ray.y*256,ray.z*256),net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
                    var pos=blockHit.getBlockPos();pick.addProperty("block",net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(mc.level.getBlockState(pos).getBlock()).toString());pick.addProperty("blockPosition",pos.toShortString());picks.add(pick);
                }
                if(stage==9&&Boolean.getBoolean("minecampus.requireMensaRetaining")){
                    int confirmed=0;
                    for(var element:picks){var pick=element.getAsJsonObject();float u=pick.get("u").getAsFloat();
                        if(Math.abs(u-.18f)<.0001f||Math.abs(u-.35f)<.0001f||Math.abs(u-.58f)<.0001f){
                            if(pick.get("tile").getAsInt()!=1_000_030_005)throw new AssertionError("Former Mensa approach still hits an old wall fragment at u="+u);
                            confirmed++;
                        }
                    }
                    if(confirmed!=3)throw new AssertionError("Missing approach diagnostic rays");
                    Files.writeString(Path.of("campus-retaining-result.txt"),"PASS: three former jagged approach fragments now hit the surveyed retaining-wall reconstruction");
                }
                Files.writeString(Path.of("campus-fragment-picks-"+stage+".json"),picks.toString());
            }
            try (var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())) {
                image.writeToFile(Path.of(NAMES[stage]));
            }
            if(Boolean.getBoolean("minecampus.inspectOnly")){Files.writeString(Path.of("campus-inspection-result.txt"),"PASS: isolated inspection frame");mc.stop();return;}
            ++stage;
            moved=false;
        } catch(Throwable error) { fail(mc,error); }
    }

    private static void fail(Minecraft mc,Throwable error) {
        error.printStackTrace();
        try {Files.writeString(Path.of("campus-client-result.txt"), "FAIL: " + error);} catch(Exception ignored) {}
        mc.stop();
    }
}
