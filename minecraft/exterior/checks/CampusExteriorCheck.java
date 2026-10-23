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
    private boolean bankStarted;
    private boolean benchmarkStarted;
    private boolean warehouseFrontVerified,cosWestVerified,cosSouthVerified;
    private volatile boolean bankVerified,bankCheckQueued;
    private int bankTicks;
    private boolean cosGroundStarted;
    private volatile boolean cosGroundVerified,cosGroundQueued;
    private int cosGroundTicks;
    private boolean cosBenchStarted;
    private volatile boolean cosBenchVerified,cosBenchQueued;
    private int cosBenchTicks;
    private boolean apronStarted;
    private volatile boolean apronVerified,apronQueued;
    private int apronTicks;
    private int ticks, stage=Boolean.getBoolean("minecampus.inspectOnly")?Integer.getInteger("minecampus.inspectStage",3):0, total, readyTicks;
    private volatile Throwable failure;
    private volatile int expectedJournal;
    private volatile boolean collisionVerified;
    private volatile boolean collisionProofQueued;
    private static final String[] NAMES = {"campus-final-ground.png", "campus-final-aerial.png", "campus-tnt.png", "campus-route-west.png", "campus-route-south.png", "campus-route-north.png", "campus-source-check.png", "campus-ias.png", "campus-photo-north.png", "campus-former-mensa.png", "campus-mensa-terrace.png", "campus-paving-detail.png", "campus-warehouse-east.png", "campus-road-detail.png", "campus-telefonzentrale-west.png", "campus-cos-southwest.png", "campus-cos-south.png", "campus-cos-aerial.png", "campus-cos-forecourt.png", "campus-cos-planting.png", "campus-cos-north.png", "campus-grs-north.png", "campus-grs-west.png", "campus-grs-tower-north.png", "campus-grs-tower-courtyard.png", "campus-grs-connectors-aerial.png", "campus-grs-main-west.png", "campus-grs-main-east.png", "campus-grs-iii-west.png", "campus-grs-iii-south.png", "campus-grs-iii-east.png", "campus-grs-iii-tower.png", "campus-grs-iii-aerial.png", "campus-grs-courtyard-path.png", "campus-grs-courtyard-connector.png"};
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
        "0 68 -238 180 0",
        "25 65 -125 90 25",
        "183 65 -231.5 90 3.5",
        "51 65 -190 0 40",
        "130 65 -269 -65 5",
        "128 65 -267 -140 -13",
        "190 65 -270 140 -15",
        "125 120 -240 -145 31",
        "162 64 -270 -171 14",
        "154 64 -272 180 20",
        "178 64 -337 0 12",
        "214 64 -342 -15 -10",
        "191 63 -314 -90 -20",
        "251 64 -318 -14 -12",
        "238 64 -292 -118 -8",
        "242 96 -310 -40 56",
        "225 64 -280 -90 -7",
        "286 64 -278 90 -7",
        "222 64 -240 -90 -7",
        "249 64 -210 180 -8",
        "278 64 -237 90 -7",
        "262 64 -255 90 -15",
        "280 105 -208 140 56",
        "262 64 -255 90 20",
        "262 64 -255 90 -15"
    };

    @Override public void onInitializeClient() {
        if(Boolean.getBoolean("minecampus.bankOnly")){
            stage=NAMES.length;walkingStarted=true;gameplayVerified=true;ticks=100;
            terraceStarted=true;terraceVerified=true;terraceTicks=120;
            roofStarted=true;roofVerified=true;roofTicks=120;
        }
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
            if (++total > 11000) throw new AssertionError("Native campus client capture timed out");
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
                if(Boolean.getBoolean("minecampus.requireFineTerrain")||Boolean.getBoolean("minecampus.bankOnly")){
                    if(!bankStarted){
                        bankStarted=true;
                        mc.getSingleplayerServer().execute(()->{
                            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                            player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s 14.5 68 -228.5 180 0");
                        });
                        return;
                    }
                    if(++bankTicks<120)return;
                    if(!bankVerified){
                        if(!bankCheckQueued){
                            bankCheckQueued=true;
                            mc.getSingleplayerServer().execute(()->{
                                try{
                                    var world=mc.getSingleplayerServer().overworld();
                                    if(!dev.realworldmc.CampusCollision.aligned(world,0,-15)){bankCheckQueued=false;return;}
                                    var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                                    // Barycentric height of the encoded DGM1 triangle at
                                    // (14.5,-228.5), independently checked by validate-terrain.py.
                                    // Native ground proxy tops round to the nearest block.
                                    if(!player.onGround()||Math.abs(player.getY()-62.378458)>.51)throw new AssertionError("Fine Mensa bank collider mismatch: "+player.getY());
                                    Files.writeString(Path.of("campus-bank-result.txt"),"PASS: native gravity landed player on the refined Mensa bank at Y="+player.getY());
                                    bankVerified=true;
                                }catch(Throwable error){failure=error;}
                            });
                        }
                        return;
                    }
                }
                if(Boolean.getBoolean("minecampus.requireCosExterior")){
                    if(!cosGroundStarted){
                        cosGroundStarted=true;
                        mc.getSingleplayerServer().execute(()->{
                            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                            player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s 186.5 69 -288.5 140 0");
                        });
                        return;
                    }
                    if(++cosGroundTicks<120)return;
                    if(!cosGroundVerified){
                        if(!cosGroundQueued){
                            cosGroundQueued=true;
                            mc.getSingleplayerServer().execute(()->{
                                try{
                                    var world=mc.getSingleplayerServer().overworld();
                                    if(!dev.realworldmc.CampusCollision.aligned(world,11,-19)){cosGroundQueued=false;return;}
                                    var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                                    if(!player.onGround()||Math.abs(player.getY()-63.153)>.51)throw new AssertionError("COS finished-site collider mismatch: "+player.getY());
                                    Files.writeString(Path.of("campus-cos-ground-result.txt"),"PASS: native gravity landed player on graded COS perimeter at Y="+player.getY()+", replacing the former construction mound");
                                    cosGroundVerified=true;
                                }catch(Throwable error){failure=error;}
                            });
                        }
                        return;
                    }
                }
                if(Boolean.getBoolean("minecampus.requireCosSite")){
                    if(!cosBenchStarted){
                        cosBenchStarted=true;
                        mc.getSingleplayerServer().execute(()->{
                            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                            player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s 156.18 68 -281.56 180 0");
                        });
                        return;
                    }
                    if(++cosBenchTicks<120)return;
                    if(!cosBenchVerified){
                        if(!cosBenchQueued){
                            cosBenchQueued=true;
                            mc.getSingleplayerServer().execute(()->{
                                try{
                                    var world=mc.getSingleplayerServer().overworld();
                                    if(!dev.realworldmc.CampusCollision.aligned(world,9,-18)){cosBenchQueued=false;return;}
                                    var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                                    if(!player.onGround()||Math.abs(player.getY()-64)>.01)throw new AssertionError("COS bench collider mismatch: "+player.getY());
                                    Files.writeString(Path.of("campus-cos-bench-result.txt"),"PASS: native gravity landed player on the bench proxy at Y="+player.getY()+"; visible seat top Y=63.89");
                                    cosBenchVerified=true;
                                }catch(Throwable error){failure=error;}
                            });
                        }
                        return;
                    }
                }
                if(Boolean.getBoolean("minecampus.requireCosLandscape")){
                    if(!apronStarted){
                        apronStarted=true;
                        mc.getSingleplayerServer().execute(()->{
                            var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                            player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                            mc.getSingleplayerServer().getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s 163.5 68 -276.5 180 0");
                        });
                        return;
                    }
                    if(++apronTicks<120)return;
                    if(!apronVerified){
                        if(!apronQueued){
                            apronQueued=true;
                            mc.getSingleplayerServer().execute(()->{
                                try{
                                    var world=mc.getSingleplayerServer().overworld();
                                    if(!dev.realworldmc.CampusCollision.aligned(world,10,-18)){apronQueued=false;return;}
                                    var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                                    if(!player.onGround()||Math.abs(player.getY()-63)>.01)throw new AssertionError("Smooth COS apron collider mismatch: "+player.getY());
                                    Files.writeString(Path.of("campus-cos-apron-result.txt"),"PASS: native gravity landed on the smooth apron proxy at Y="+player.getY()+" (mesh Y=63.46271), replacing the previous Y=64 proxy");
                                    apronVerified=true;
                                }catch(Throwable error){failure=error;}
                            });
                        }
                        return;
                    }
                }
                if(!Boolean.getBoolean("minecampus.bankOnly"))Files.writeString(Path.of("campus-client-result.txt"),"PASS: twenty-three ground, aerial, TNT, promenade, source-limit, IAS, photographic facade, former Mensa, paving-detail, warehouse, road-detail, Telefonzentrale and COS frames captured after full streaming readiness");mc.stop();return;
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
                        server.getCommands().performPrefixedCommand(source, "gamerule doDaylightCycle false");
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
            if(Boolean.getBoolean("minecampus.materialBenchmark")){
                // Streaming and the controlled comparison each get their own
                // bounded interval; slow provider loading must not consume
                // the last comparison phase's time budget.
                if(!benchmarkStarted){benchmarkStarted=true;total=0;}
                CampusMaterialBenchmark.tick(mc);return;
            }
            if(stage==15&&Boolean.getBoolean("minecampus.requireCosExterior"))verifyTextureSampling(mc,loaded);
            if(stage==10&&Boolean.getBoolean("minecampus.requireMensaFront")&&!((java.util.List<?>)df.get(renderer)).contains(1_000_030_005))throw new AssertionError("Former Mensa structural frontage was not displayed");
            if(stage==9&&Boolean.getBoolean("minecampus.requireVisibleFacade")&&!((java.util.List<?>)df.get(renderer)).contains(1_000_050_038))throw new AssertionError("Visible former Mensa facade was not accepted/displayed");
            if(stage==6&&Boolean.getBoolean("minecampus.requirePhotographicFacade")&&!((java.util.List<?>)df.get(renderer)).contains(1_000_050_000))throw new AssertionError("Photographic facade was not accepted/displayed");
            if((stage==6||stage==8)&&Boolean.getBoolean("minecampus.requireUyaExterior")&&!((java.util.List<?>)df.get(renderer)).contains(1_000_030_006))throw new AssertionError("UYA exterior reconstruction was not displayed");
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
            try (var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())) {
                image.writeToFile(Path.of(NAMES[stage]));
            }
            if(stage==0||stage==3||stage==5||stage==6||stage==9||stage==10||stage==12||stage==14||stage==15||stage==16||stage==17||stage==18||stage==19||stage==21||stage==22||stage==23||stage==24||stage==25||stage==26||stage==27||stage>=28&&stage<=34){
                var picks=new com.google.gson.JsonArray();
                var camera=mc.gameRenderer.getMainCamera();
                var fovMethod=net.minecraft.client.renderer.GameRenderer.class.getDeclaredMethod("getFov",net.minecraft.client.Camera.class,float.class,boolean.class);fovMethod.setAccessible(true);
                double actualFov=((Number)fovMethod.invoke(mc.gameRenderer,camera,1.0f,true)).doubleValue();
                float tanHalf=(float)Math.tan(Math.toRadians(actualFov)*.5);
                float[][] pixelsToPick=new float[][]{{.81f,.435f},{.38f,.443f}};
                if(stage==6)pixelsToPick=new float[][]{{.75f,.46f},{.8f,.5f},{.9f,.45f},{.38f,.38f},{.37f,.43f},{.766f,.55f},{.12f,.6f},{.22f,.56f}};
                if(stage==12)pixelsToPick=new float[][]{{.5f,.5f},{.80f,.49f},{.88f,.48f},{.93f,.43f}};
                if(stage==14){
                    var eye=camera.getPosition();var forward=new org.joml.Vector3f(camera.getLookVector());
                    var right=new org.joml.Vector3f(forward).cross(0,1,0).normalize();var up=new org.joml.Vector3f(right).cross(forward).normalize();
                    float[] centres={2.45f,4.70f,7.55f,9.80f};pixelsToPick=new float[4][2];
                    for(int i=0;i<centres.length;i++){
                        double x=146.5033-.1784054*centres[i]+.9839571*.18,z=-268.4920+.9839571*centres[i]+.1784054*.18;
                        var target=new org.joml.Vector3f((float)(x-eye.x),(float)(65.71065-eye.y),(float)(z-eye.z));float depth=target.dot(forward);
                        pixelsToPick[i]=new float[]{(float)(.5+.5*target.dot(right)/(depth*tanHalf*16/9)),(float)(.5-.5*target.dot(up)/(depth*tanHalf))};
                        if(pixelsToPick[i][0]<=0||pixelsToPick[i][0]>=1||pixelsToPick[i][1]<=0||pixelsToPick[i][1]>=1)throw new AssertionError("Telefonzentrale window outside verification frame");
                    }
                }
                if(stage==10)pixelsToPick=new float[][]{{.15f,.55f},{.5f,.55f},{.85f,.55f}};
                if(stage==9)pixelsToPick=new float[][]{{.78f,.35f},{.84f,.43f},{.96f,.40f},{.265f,.58f},{.51f,.59f},{.65f,.48f},{.745f,.615f},{.1f,.6f},{.18f,.55f},{.35f,.58f},{.58f,.56f},{.7f,.55f},{.82f,.41f}};
                if(stage==15||stage==16||stage==17||stage==18||stage==19||stage==21||stage==22||stage==23||stage==24||stage==25||stage==26||stage==27||stage>=28&&stage<=34){
                    double[][] targets=new double[3][3];
                    if(stage==15){double[] along={2.5,19.599,36.699};for(int i=0;i<3;i++)targets[i]=new double[]{152.840612+.1777*along[i],73.1068,-284.946-.9841*along[i]};}
                    else if(stage==16){double[] along={9.2,14,24};for(int i=0;i<3;i++)targets[i]=new double[]{152.840612+.9841*along[i],i==0?64.7568:72.9318,-284.946+.1777*along[i]};}
                    else if(stage==17)targets=new double[][]{{162.13979,83.53372,-300.74671}};
                    else if(stage==18)targets=new double[][]{{156.18110002,63.86805525,-281.56091937},{159.19933975,63.87231641,-279.42592084},{169.88380222,64.25619879,-275.68384465}};
                    else if(stage==19)targets=new double[][]{{154.04,63.4430609,-278.63},{155.10681093,63.69976512,-275.54448472}};
                    else if(stage==21){double[] along={6.25,23.75,41.25};for(int i=0;i<3;i++)targets[i]=new double[]{198.944981+.983999*along[i],69.5,-317.497887+.178174*along[i]};}
                    else if(stage==22){double[] along={2.5,6.2,10};for(int i=0;i<3;i++)targets[i]=new double[]{196.729424+.178396*along[i],69.5,-305.276602-.983959*along[i]};}
                    else if(stage==23)targets=new double[][]{{255.8,68.5,-304.55},{248.5,67,-303.08}};
                    else if(stage==24)targets=new double[][]{{252.71,65.2,-299.20},{248,67,-301.45},{247.83,66.5,-294.39}};
                    else if(stage==25)targets=new double[][]{{255.3,72.704,-301},{248.2,68.729,-302.2},{254.5,72.104,-296.5},{262,72.119,-280}};
                    else if(stage==26){double[] along={5,17,29};for(int i=0;i<3;i++)targets[i]=new double[]{241.939669+.1779618*along[i],66.5,-261.818435-.9840374*along[i]};}
                    else if(stage==27){double[] along={5,17,29};for(int i=0;i<3;i++)targets[i]=new double[]{271.851939-.1792575*along[i],66.5,-292.060924+.9838022*along[i]};}
                    else if(stage==28)targets=new double[][]{{236.709493,65.300000,-232.691777},{238.137282,67.300000,-240.545066},{239.565071,70.300000,-248.398355}};
                    else if(stage==29)targets=new double[][]{{239.929903,65.300000,-228.044689},{247.774517,67.300000,-226.629455},{255.619131,70.300000,-225.214220}};
                    else if(stage==30)targets=new double[][]{{260.265683,65.300000,-228.438349},{261.682621,67.300000,-236.285374},{263.099560,70.300000,-244.132398}};
                    else if(stage==31)targets=new double[][]{{251.30,68,-255.4},{249.3,67,-252.8}};
                    else if(stage==32)targets=new double[][]{{246.593168,73.385192,-238.988457},{245,74.681,-256}};
                    else if(stage==33)targets=new double[][]{{258,63.84,-254.151},{254,63.82,-254.864},{257.811305,63.851526,-255.098095}};
                    else if(stage==34)targets=new double[][]{{251.30,68,-255.4},{249.3,67,-252.8},{255.351174,68.8,-259.074938}};
                    var eye=camera.getPosition();var forward=new org.joml.Vector3f(camera.getLookVector());var right=new org.joml.Vector3f(forward).cross(0,1,0).normalize();var up=new org.joml.Vector3f(right).cross(forward).normalize();pixelsToPick=new float[targets.length][2];
                    for(int i=0;i<targets.length;i++){var q=targets[i];var target=new org.joml.Vector3f((float)(q[0]-eye.x),(float)(q[1]-eye.y),(float)(q[2]-eye.z));float depth=target.dot(forward);pixelsToPick[i]=new float[]{(float)(.5+.5*target.dot(right)/(depth*tanHalf*16/9)),(float)(.5-.5*target.dot(up)/(depth*tanHalf))};
                        if(depth<=0||pixelsToPick[i][0]<=0||pixelsToPick[i][0]>=1||pixelsToPick[i][1]<=0||pixelsToPick[i][1]>=1)throw new AssertionError("COS target outside verification frame");
                    }
                }
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
                if(stage==34){pixelsToPick[0]=new float[]{.61f,.30f};pixelsToPick[1]=new float[]{.61f,.42f};}
                for(float[] pixel:pixelsToPick){
                    var forward=new org.joml.Vector3f(camera.getLookVector());
                    var right=new org.joml.Vector3f(forward).cross(0,1,0).normalize();
                    var up=new org.joml.Vector3f(right).cross(forward).normalize();
                    var ray=new org.joml.Vector3f(forward).add(right.mul((pixel[0]*2-1)*tanHalf*16/9)).add(up.mul((1-pixel[1]*2)*tanHalf)).normalize();
                    var eye=camera.getPosition();float nearest=10000,nearestStructure=10000;int hit=-1,structureHit=-1;double[] structureTriangle=null;
                    for(var item:loaded.values()){
                        var tile=(MapTile)item;var data=tile.data;
                        if(!((java.util.List<?>)df.get(renderer)).contains(data.id))continue;
                        for(var part:data.parts){var v=part.vertices;
                            for(int o=0;o<v.length;o+=15){
                                float t=org.joml.Intersectionf.intersectRayTriangle((float)(eye.x-data.anchorX),(float)(eye.y-data.anchorY),(float)(eye.z-data.anchorZ),ray.x,ray.y,ray.z,v[o],v[o+1],v[o+2],v[o+5],v[o+6],v[o+7],v[o+10],v[o+11],v[o+12],1e-6f);
                                if(t>0&&t<nearest){nearest=t;hit=data.id;}
                                if(t>0&&t<nearestStructure&&(data.id<1_000_010_000||data.id>=1_000_020_000)){nearestStructure=t;structureHit=data.id;structureTriangle=new double[]{v[o]+data.anchorX,v[o+1]+data.anchorY,v[o+2]+data.anchorZ,v[o+5]+data.anchorX,v[o+6]+data.anchorY,v[o+7]+data.anchorZ,v[o+10]+data.anchorX,v[o+11]+data.anchorY,v[o+12]+data.anchorZ};}
                            }
                        }
                    }
                    var pick=new com.google.gson.JsonObject();var region=dev.realworldmc.EarthRegions.at((int)Math.floor(eye.x),(int)Math.floor(eye.z));if(region!=null)pick.addProperty("frameGroundHeight",region.groundHeight());pick.addProperty("u",pixel[0]);pick.addProperty("v",pixel[1]);pick.addProperty("fov",actualFov);pick.addProperty("tile",hit);pick.addProperty("x",eye.x+ray.x*nearest);pick.addProperty("y",eye.y+ray.y*nearest);pick.addProperty("z",eye.z+ray.z*nearest);var blockHit=mc.level.clip(new net.minecraft.world.level.ClipContext(eye,eye.add(ray.x*256,ray.y*256,ray.z*256),net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
                    var pos=blockHit.getBlockPos();pick.addProperty("block",net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(mc.level.getBlockState(pos).getBlock()).toString());pick.addProperty("blockPosition",pos.toShortString());pick.addProperty("structureBehindVegetation",structureHit);pick.addProperty("structureDistance",nearestStructure);if(structureTriangle!=null){var triangle=new com.google.gson.JsonArray();for(double value:structureTriangle)triangle.add(value);pick.add("structureTriangle",triangle);}picks.add(pick);
                }
                Files.writeString(Path.of("campus-fragment-picks-"+stage+".json"),picks.toString());
                if(stage==9&&Boolean.getBoolean("minecampus.requireMensaRetaining")){
                    int confirmed=0;
                    for(var element:picks){var pick=element.getAsJsonObject();float u=pick.get("u").getAsFloat();
                        if(Math.abs(u-.18f)<.0001f||Math.abs(u-.35f)<.0001f||Math.abs(u-.58f)<.0001f){
                            if(pick.get("structureBehindVegetation").getAsInt()!=1_000_030_005)throw new AssertionError("Former Mensa approach still hits an old wall fragment behind vegetation at u="+u);
                            confirmed++;
                        }
                    }
                    if(confirmed!=3)throw new AssertionError("Missing approach diagnostic rays");
                    Files.writeString(Path.of("campus-retaining-result.txt"),"PASS: three former jagged approach fragments now hit the surveyed retaining-wall reconstruction");
                }
                if(stage==9&&Boolean.getBoolean("minecampus.requireMensaCanopy")){
                    int confirmed=0;
                    for(var element:picks){var pick=element.getAsJsonObject();float u=pick.get("u").getAsFloat();
                        if(Math.abs(u-.84f)<.0001f||Math.abs(u-.82f)<.0001f){
                            // Ignore the new foliage when checking for the old fragments:
                            // covering a broken triangle is not evidence it was removed.
                            if(pick.get("structureBehindVegetation").getAsInt()>=1_100_000_000&&pick.get("structureDistance").getAsFloat()<30)throw new AssertionError("Original near-terrace canopy fragment survives behind new foliage at u="+u);
                            confirmed++;
                        }
                    }
                    if(confirmed!=2)throw new AssertionError("Missing canopy diagnostic rays");
                    Files.writeString(Path.of("campus-canopy-result.txt"),"PASS: two original near-terrace scan fragments are absent, including behind reconstructed foliage");
                }
                if(stage==6&&Boolean.getBoolean("minecampus.requireUyeExterior")){
                    boolean found=false;
                    for(var entry:picks){var pick=entry.getAsJsonObject();
                        if(Math.abs(pick.get("u").getAsFloat()-.9f)<.001){
                            if(pick.get("structureBehindVegetation").getAsInt()!=1_000_030_007)throw new AssertionError("UYE foreground ray still hits old photographic wall");
                            found=true;
                        }
                    }
                    if(!found)throw new AssertionError("Missing UYE foreground diagnostic ray");
                    Files.writeString(Path.of("campus-uye-result.txt"),"PASS: foreground UYE ray hits the reconstructed roof fascia/glazing envelope");
                }
                if(Boolean.getBoolean("minecampus.requireWarehouseExterior")&&(stage==6||stage==12)){
                    int confirmed=0;
                    for(var entry:picks){var pick=entry.getAsJsonObject();float u=pick.get("u").getAsFloat();
                        if((stage==12&&Math.abs(u-.5f)<.001)||(stage==6&&(Math.abs(u-.12f)<.001||Math.abs(u-.22f)<.001))){
                            if(pick.get("structureBehindVegetation").getAsInt()!=1_000_030_008)throw new AssertionError("Warehouse ray still hits old source geometry at stage="+stage+" u="+u);
                            confirmed++;
                        }
                    }
                    if(stage==6){if(confirmed!=2)throw new AssertionError("Missing warehouse route rays");warehouseFrontVerified=true;}
                    else{
                        if((!warehouseFrontVerified&&!Boolean.getBoolean("minecampus.inspectOnly"))||confirmed!=1)throw new AssertionError("Warehouse route/east view incomplete");
                        Files.writeString(Path.of("campus-warehouse-result.txt"),"PASS: two former blurred foreground rays and the east-opening ray hit the warehouse reconstruction");
                    }
                }
                if(Boolean.getBoolean("minecampus.requireCosExterior")&&(stage==15||stage==16||stage==17)){
                    if(picks.size()!=(stage==17?1:3))throw new AssertionError("Missing COS diagnostic rays");
                    for(var entry:picks)if(entry.getAsJsonObject().get("structureBehindVegetation").getAsInt()!=1_000_030_010)throw new AssertionError("COS ray retains obsolete site geometry at stage "+stage);
                    if(stage==15)cosWestVerified=true;
                    else if(stage==16)cosSouthVerified=true;
                    else{if((!cosWestVerified||!cosSouthVerified)&&!Boolean.getBoolean("minecampus.inspectOnly"))throw new AssertionError("COS ground views missing");Files.writeString(Path.of("campus-cos-result.txt"),"PASS: six ground-level rays and one aerial roof ray hit the COS reconstruction; current building survives aerial mode");}
                }
                if(Boolean.getBoolean("minecampus.requireCosSite")&&stage==18){
                    if(picks.size()!=3)throw new AssertionError("Missing COS furniture diagnostic rays");
                    for(var entry:picks)if(entry.getAsJsonObject().get("tile").getAsInt()!=1_000_030_011)throw new AssertionError("COS furniture ray does not reach the visible reconstruction");
                    Files.writeString(Path.of("campus-cos-site-result.txt"),"PASS: both mapped benches and a bicycle stand are visible in the packaged native renderer");
                }
                if(Boolean.getBoolean("minecampus.requireGrsExterior")&&(stage==21||stage==22)){
                    if(picks.size()!=3)throw new AssertionError("Missing GRS facade rays");
                    for(var entry:picks)if(entry.getAsJsonObject().get("tile").getAsInt()!=1_000_030_012)throw new AssertionError("GRS facade ray misses reconstruction");
                    Files.writeString(Path.of("campus-grs-"+(stage==21?"north":"west")+"-result.txt"),"PASS: three native facade rays reach the surveyed GRS reconstruction after streaming readiness");
                }
                if(Boolean.getBoolean("minecampus.requireGrsConnectors")&&stage>=23&&stage<=25){
                    // Roof geometry must persist beneath foliage; ground rays require a direct visible hit.
                    int[] expected=stage==25?new int[]{1_000_030_013,1_000_030_014,1_000_030_015,1_000_030_016}:stage==24?new int[]{1_000_030_013,1_000_030_014,1_000_030_016}:new int[]{1_000_030_013,1_000_030_014};
                    if(picks.size()!=expected.length)throw new AssertionError("Missing GRS connector rays");
                    for(int i=0;i<expected.length;i++)if(picks.get(i).getAsJsonObject().get(stage==25?"structureBehindVegetation":"tile").getAsInt()!=expected[i])throw new AssertionError("GRS connector/neighbour ray misses expected structure at stage "+stage+" ray "+i+": "+picks.get(i));
                    Files.writeString(Path.of("campus-grs-connectors-"+(stage==23?"north":stage==24?"courtyard":"aerial")+"-result.txt"),"PASS: native rays reach the tower and west link"+(stage==25?", the south junction and preserved adjoining GRS roof behind any foliage":stage==24?" and the repaired GRS II west facade at walking height":" at walking height"));
                }
                if(Boolean.getBoolean("minecampus.requireGrsMain")&&(stage==26||stage==27)){
                    if(picks.size()!=3)throw new AssertionError("Missing GRS II facade rays");
                    for(var entry:picks)if(entry.getAsJsonObject().get("structureBehindVegetation").getAsInt()!=1_000_030_016)throw new AssertionError("GRS II facade ray passes through the surveyed exterior at stage "+stage);
                    Files.writeString(Path.of("campus-grs-main-"+(stage==26?"west":"east")+"-result.txt"),"PASS: three native rays stop at the repaired surveyed GRS II facade behind any foliage");
                }
                if(Boolean.getBoolean("minecampus.requireGrsIII")&&stage>=28&&stage<=32){
                    if(picks.size()!=(stage<=30?3:2))throw new AssertionError("Missing GRS III diagnostic rays");
                    for(var entry:picks)if(entry.getAsJsonObject().get("structureBehindVegetation").getAsInt()!=1_000_030_017)throw new AssertionError("GRS III ray misses reconstructed exterior at stage "+stage+": "+entry);
                    String[] names={"west","south","east","tower","aerial"};
                    Files.writeString(Path.of("campus-grs-iii-"+names[stage-28]+"-result.txt"),"PASS: native rays reach GRS III's surveyed facade, tower or preserved raised roof behind any foliage");
                }
                if(Boolean.getBoolean("minecampus.requireGrsCourtyard")&&stage==34){
                    var high=picks.get(0).getAsJsonObject();
                    if(high.get("structureBehindVegetation").getAsInt()>=1_100_000_000&&high.get("structureDistance").getAsDouble()<30)throw new AssertionError("Upper connector scan fragment survives");
                    if(picks.get(1).getAsJsonObject().get("structureBehindVegetation").getAsInt()!=1_000_030_018)throw new AssertionError("Lower connector ray misses replacement: "+picks.get(1));
                    if(picks.get(2).getAsJsonObject().get("structureBehindVegetation").getAsInt()!=1_000_030_016)throw new AssertionError("Neighbouring GRS II facade was not preserved");
                    Files.writeString(Path.of("campus-grs-courtyard-connector-result.txt"),"PASS: upper scan fragment absent, lower fragment replaced by surveyed connector and adjacent GRS II facade preserved");
                }
                if(Boolean.getBoolean("minecampus.requireGrsCourtyard")&&stage==33){
                    var maskLocation=net.minecraft.resources.ResourceLocation.fromNamespaceAndPath("realworldmc","textures/campus/ground_surfaces.png");
                    try(var stream=mc.getResourceManager().getResourceOrThrow(maskLocation).open();var mask=com.mojang.blaze3d.platform.NativeImage.read(stream)){
                        for(int i=0;i<2;i++){
                            var pick=picks.get(i).getAsJsonObject();int tile=pick.get("tile").getAsInt();
                            if(tile<1_000_000_000||tile>=1_000_000_036)throw new AssertionError("Courtyard paving ray misses surveyed terrain: "+pick);
                            int x=(int)((pick.get("x").getAsDouble()+352)/672*4096),y=(int)((256-pick.get("z").getAsDouble())/672*4096);
                            if(mask.getPixelRGBA(x,y)!=0xFF00FF00)throw new AssertionError("Courtyard ray misses paving material mask");
                        }
                    }
                    if(picks.get(2).getAsJsonObject().get("tile").getAsInt()!=1_000_030_019)throw new AssertionError("Courtyard low-edge ray misses edging: "+picks.get(2));
                    Files.writeString(Path.of("campus-grs-courtyard-path-result.txt"),"PASS: two walking-view rays reach the paving mask on unchanged surveyed terrain, and a third reaches the low edging");
                }
                if(Boolean.getBoolean("minecampus.requireCosLandscape")&&stage==19){
                    if(picks.size()!=2)throw new AssertionError("Missing COS landscape rays");
                    var soil=picks.get(0).getAsJsonObject();int tile=soil.get("tile").getAsInt();
                    if(tile<1_000_000_000||tile>=1_000_000_036)throw new AssertionError("Planting-bed ray does not reach surveyed ground");
                    var curb=picks.get(1).getAsJsonObject();
                    if(curb.get("tile").getAsInt()!=1_000_030_011||Math.abs(curb.get("y").getAsDouble()-63.69977)>.03)throw new AssertionError("Planting-bed edging ray does not reach the low curb");
                    var maskLocation=net.minecraft.resources.ResourceLocation.fromNamespaceAndPath("realworldmc","textures/campus/ground_surfaces.png");
                    try(var stream=mc.getResourceManager().getResourceOrThrow(maskLocation).open();var mask=com.mojang.blaze3d.platform.NativeImage.read(stream)){
                        int x=(int)((soil.get("x").getAsDouble()+352)/672*4096),y=(int)((256-soil.get("z").getAsDouble())/672*4096);
                        if(mask.getPixelRGBA(x,y)!=0)throw new AssertionError("Native soil ray misses the inverse-alpha soil material mask");
                    }
                    try(var frame=Screenshot.takeScreenshot(mc.getMainRenderTarget())){
                        int x=(int)(soil.get("u").getAsFloat()*frame.getWidth()),y=(int)(soil.get("v").getAsFloat()*frame.getHeight());double red=0,green=0,blue=0;
                        for(int dy=-2;dy<=2;dy++)for(int dx=-2;dx<=2;dx++){int pixel=frame.getPixelRGBA(x+dx,y+dy);red+=pixel&255;green+=(pixel>>>8)&255;blue+=(pixel>>>16)&255;}
                        red/=25*255.;green/=25*255.;blue/=25*255.;
                        if((red+green+blue)/3>.55||red<blue*1.05)throw new AssertionError("Soil still renders as pale construction imagery: "+red+","+green+","+blue);
                        Files.writeString(Path.of("campus-cos-landscape-result.txt"),"PASS: bed ray reaches surveyed ground with the soil mask and brown rendered texture (RGB "+red+","+green+","+blue+"); exposed curb ray reaches its 12cm edging");
                    }
                }
                if(Boolean.getBoolean("minecampus.requireTelefonzentraleExterior")&&stage==14){
                    if(picks.size()!=4)throw new AssertionError("Missing Telefonzentrale window rays");
                    for(var entry:picks)if(entry.getAsJsonObject().get("structureBehindVegetation").getAsInt()!=1_000_030_009)throw new AssertionError("Telefonzentrale window ray does not hit its reconstructed facade");
                    Files.writeString(Path.of("campus-telefonzentrale-result.txt"),"PASS: all four west-window rays hit the reconstruction on the correct 5130 survey envelope");
                }
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
    private static void verifyTextureSampling(Minecraft mc,java.util.Map<?,?> loaded) throws Exception {
        var location=net.minecraft.resources.ResourceLocation.fromNamespaceAndPath("realworldmc","shaders/core/campus_ground.fsh");
        var resource=mc.getResourceManager().getResourceOrThrow(location);
        byte[] actual,packaged;
        try(var in=resource.open()){actual=in.readAllBytes();}
        try(var in=MapRenderer.class.getResourceAsStream("/assets/realworldmc/shaders/core/campus_ground.fsh")){packaged=in.readAllBytes();}
        if(!resource.sourcePackId().equals("realworldmc")||!java.util.Arrays.equals(actual,packaged))throw new AssertionError("Native check has a shader resource override");
        var proof=new com.google.gson.JsonObject();proof.addProperty("shaderSha256",java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(actual)));
        var samplers=new com.google.gson.JsonArray();
        var textures=new java.util.ArrayList<Integer>();
        for(int id:new int[]{1_000_030_010,1_000_000_000}){
            var tile=(MapTile)loaded.get(id);if(tile==null)throw new AssertionError("Missing sampler probe tile "+id);
            textures.add(tile.textureId(0));
        }
        var prepared=CampusMaterials.class.getDeclaredField("prepared");prepared.setAccessible(true);
        for(int id:(int[])prepared.get(null)){if(id<0)throw new AssertionError("Shared material not prepared");textures.add(id);}
        int active=org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL13.GL_ACTIVE_TEXTURE);
        com.mojang.blaze3d.platform.GlStateManager._activeTexture(org.lwjgl.opengl.GL13.GL_TEXTURE0);
        int previous=org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL11.GL_TEXTURE_BINDING_2D);
        try{
            for(int id:textures){
                com.mojang.blaze3d.platform.GlStateManager._bindTexture(id);
                int filter=org.lwjgl.opengl.GL11.glGetTexParameteri(org.lwjgl.opengl.GL11.GL_TEXTURE_2D,org.lwjgl.opengl.GL11.GL_TEXTURE_MIN_FILTER);
                int level=org.lwjgl.opengl.GL11.glGetTexParameteri(org.lwjgl.opengl.GL11.GL_TEXTURE_2D,org.lwjgl.opengl.GL12.GL_TEXTURE_MAX_LEVEL);
                float maxLod=org.lwjgl.opengl.GL11.glGetTexParameterf(org.lwjgl.opengl.GL11.GL_TEXTURE_2D,org.lwjgl.opengl.GL12.GL_TEXTURE_MAX_LOD);
                int width=org.lwjgl.opengl.GL11.glGetTexLevelParameteri(org.lwjgl.opengl.GL11.GL_TEXTURE_2D,level,org.lwjgl.opengl.GL11.GL_TEXTURE_WIDTH);
                if(filter!=org.lwjgl.opengl.GL11.GL_LINEAR_MIPMAP_LINEAR||level<1||maxLod<level||width<1)throw new AssertionError("Texture mipmaps unavailable or clamped: "+filter+" / "+level+" / "+maxLod+" / "+width);
                var sample=new com.google.gson.JsonObject();sample.addProperty("maxLevel",level);sample.addProperty("maxLod",maxLod);sample.addProperty("lastMipWidth",width);samplers.add(sample);
            }
        }finally{
            com.mojang.blaze3d.platform.GlStateManager._bindTexture(previous);
            com.mojang.blaze3d.platform.GlStateManager._activeTexture(active);
        }
        proof.add("samplers",samplers);Files.writeString(Path.of("campus-texture-sampling.json"),proof.toString());
        Files.writeString(Path.of("campus-texture-result.txt"),"PASS: packaged shader active; ten map/shared material textures use generated mipmaps with sampling clamps lifted");
    }

}
