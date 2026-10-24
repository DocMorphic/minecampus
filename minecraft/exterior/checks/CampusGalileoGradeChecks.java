package dev.realworldmc.client;

import com.google.gson.*;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.GameType;
import java.nio.file.*;

/** Isolated native gravity probes over three former source-terrain pits. */
public final class CampusGalileoGradeChecks {
    private static final double[][] PROBES={{66.5,-58.5},{65.5,-49.5},{72.5,-73.5}};
    private static final double[] expected=new double[PROBES.length];
    private static final JsonArray report=new JsonArray();
    private static int index,ticks;
    private static volatile boolean queued,ready,checking;
    private static volatile Throwable failure;
    public static void begin(Minecraft mc,java.util.Map<?,?> loaded)throws Exception{
        if(!MapRenderer.class.getProtectionDomain().getCodeSource().getLocation().toString().endsWith(".jar"))throw new AssertionError("Frontage check requires packaged renderer");
        var field=MapRenderer.class.getDeclaredField("displayed");field.setAccessible(true);
        var displayed=(java.util.List<?>)field.get(MapRenderer.INSTANCE);
        for(int i=0;i<PROBES.length;i++){
            double x=PROBES[i][0],z=PROBES[i][1];float distance=1000;int hit=-1,partHit=-1;
            for(var value:loaded.values()){
                var tile=(MapTile)value;var d=tile.data;
                if(!displayed.contains(d.id))continue;
                if(d.id>=1_000_010_000&&d.id<1_000_020_000)continue;
                for(int pi=0;pi<d.parts.length;pi++){var v=d.parts[pi].vertices;
                    for(int o=0;o<v.length;o+=15){
                        float t=org.joml.Intersectionf.intersectRayTriangle((float)(x-d.anchorX),(float)(80-d.anchorY),(float)(z-d.anchorZ),0,-1,0,v[o],v[o+1],v[o+2],v[o+5],v[o+6],v[o+7],v[o+10],v[o+11],v[o+12],1e-6f);
                        if(t>0&&t<distance){distance=t;hit=d.id;partHit=pi;}
                    }
                }
            }
            if(hit!=1_000_000_020||partHit!=0)throw new AssertionError("Frontage landing obstructed or missing at "+x+", "+z+": tile "+hit+", part "+partHit);
            expected[i]=80-distance;
            if(expected[i]<64.65||expected[i]>65.5)throw new AssertionError("Frontage grade still contains a deep depression: "+expected[i]);
        }
    }
    public static boolean tick(Minecraft mc)throws Exception{
        if(failure!=null)throw new AssertionError("Frontage walking check failed",failure);
        if(index==PROBES.length){
            var result=new JsonObject();result.addProperty("status","PASS: three former frontage pits now support native gravity on reconstructed paving within the existing half-block proxy tolerance");result.addProperty("rendererJar",Path.of(MapRenderer.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getFileName().toString());result.add("probes",report);
            Files.writeString(Path.of("campus-galileo-grade-collision.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));return true;
        }
        var server=mc.getSingleplayerServer();
        if(!queued){
            queued=true;ready=false;checking=false;ticks=0;
            server.execute(()->{try{
                var player=server.getPlayerList().getPlayer(mc.player.getUUID());player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"tp @s "+PROBES[index][0]+" "+(expected[index]+7)+" "+PROBES[index][1]);ready=true;
            }catch(Throwable e){failure=e;}});return false;
        }
        if(!ready||++ticks<100||checking)return false;
        checking=true;
        server.execute(()->{try{
            var player=server.getPlayerList().getPlayer(mc.player.getUUID());
            if(!player.onGround()||Math.abs(player.getY()-expected[index])>.51)throw new AssertionError("Probe "+index+" landed at "+player.getY()+"; mesh at "+expected[index]);
            var chunk=player.chunkPosition();if(!dev.realworldmc.CampusCollision.aligned(server.overworld(),chunk.x,chunk.z))throw new AssertionError("Frontage chunk has not completed collision migration");
            var row=new JsonObject();row.addProperty("x",PROBES[index][0]);row.addProperty("z",PROBES[index][1]);row.addProperty("meshHeight",expected[index]);row.addProperty("standingY",player.getY());row.addProperty("onGround",player.onGround());report.add(row);index++;queued=false;
        }catch(Throwable e){failure=e;}});return false;
    }
}
