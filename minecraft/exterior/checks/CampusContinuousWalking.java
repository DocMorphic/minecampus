package dev.realworldmc.client;

import com.google.gson.*;
import java.nio.file.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;

/** Isolated QA: ordinary forward/jump input between endpoints; no mid-route teleport. */
public final class CampusContinuousWalking {
    private static JsonObject plan, current;
    private static final JsonArray completed = new JsonArray(), samples = new JsonArray();
    private static int routeIndex, pointIndex, ticks, settleTicks, stalledTicks, movementTicks, jumps;
    private static volatile boolean startReady;
    private static volatile Throwable failure;
    private static boolean started, moving;
    private static double lastX, lastZ, travelled, nextCapture;

    private static void release(Minecraft mc) {
        mc.options.keyUp.setDown(false);
        mc.options.keyJump.setDown(false);
        mc.options.keySprint.setDown(false);
    }
    private static void report(String status) throws Exception {
        var d = new JsonObject(); d.addProperty("status",status); d.add("plan",plan);
        d.add("completed",completed); d.add("samples",samples);
        d.addProperty("routeIndex",routeIndex); d.addProperty("waypointIndex",pointIndex);
        d.addProperty("travelledMetres",travelled); d.addProperty("movementTicks",movementTicks);
        d.addProperty("jumps",jumps);
        String text=new GsonBuilder().setPrettyPrinting().create().toJson(d);
        Files.writeString(Path.of("campus-"+plan.get("name").getAsString()+"-routes.json"),text);
        Files.writeString(Path.of("campus-"+plan.get("name").getAsString()+"-result.json"),text);
    }
    private static void capture(Minecraft mc, JsonObject row, String suffix) throws Exception {
        String filename="campus-"+plan.get("name").getAsString()+"-route-"+routeIndex+"-"+suffix+".png";
        try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of(filename));}
        row.addProperty("capture",filename);
    }
    public static void tick(Minecraft mc, boolean ready) throws Exception {
        try { step(mc,ready); }
        catch(Throwable error){
            release(mc);
            if(plan!=null){var row=new JsonObject();row.addProperty("error",error.toString());row.addProperty("position",mc.player.position().toString());capture(mc,row,"failure");samples.add(row);report("FAIL: "+error.getMessage());}
            throw new AssertionError("Continuous walking failed",error);
        }
    }
    private static void step(Minecraft mc, boolean ready) throws Exception {
        release(mc);
        if(plan==null){
            plan=JsonParser.parseString(Files.readString(Path.of("site-inspection.json"))).getAsJsonObject();
            if(!plan.get("name").getAsString().matches("[a-z0-9-]+"))throw new IllegalArgumentException("Invalid plan name");
            if(!plan.has("walkingRoutes")||plan.getAsJsonArray("walkingRoutes").isEmpty())throw new IllegalArgumentException("No walking routes");
            mc.options.autoJump().set(false);
        }
        if(failure!=null)throw new AssertionError(failure);
        if(routeIndex==plan.getAsJsonArray("walkingRoutes").size()) {report("PASS: continuous input-driven walking routes; visual review required");mc.stop();return;}
        if(++ticks>2400)throw new AssertionError(started ? "Route exceeded120seconds after readiness" : "Initial route readiness exceeded120seconds");
        if(!ready||mc.screen!=null)return;
        current=plan.getAsJsonArray("walkingRoutes").get(routeIndex).getAsJsonObject();
        var points=current.getAsJsonArray("points");
        if(!started){
            // Initial tile loading has its own bounded allowance; movement limits stay unchanged.
            started=true;ticks=0;startReady=false;settleTicks=0;movementTicks=0;jumps=0;travelled=0;nextCapture=5;stalledTicks=0;pointIndex=1;
            var first=points.get(0).getAsJsonArray();var uuid=mc.player.getUUID();var server=mc.getSingleplayerServer();
            server.execute(()->{try{
                var p=server.getPlayerList().getPlayer(uuid);p.setGameMode(net.minecraft.world.level.GameType.CREATIVE);p.getAbilities().flying=false;p.onUpdateAbilities();
                server.getCommands().performPrefixedCommand(p.createCommandSourceStack().withPermission(4),"tp @s "+first.get(0).getAsDouble()+" "+(first.get(1).getAsDouble()+1)+" "+first.get(2).getAsDouble());
                startReady=true;
            }catch(Throwable error){failure=error;}});return;
        }
        if(!startReady||++settleTicks<80)return;
        var player=mc.player;
        if(!moving){
            if(!player.onGround()||player.getAbilities().flying)throw new AssertionError("Route start did not settle on foot");
            moving=true;lastX=player.getX();lastZ=player.getZ();var row=new JsonObject();row.addProperty("event","start");row.addProperty("route",routeIndex);row.addProperty("position",player.position().toString());capture(mc,row,"start");samples.add(row);
        }
        if(player.getAbilities().flying)throw new AssertionError("Unexpected flight during walking");
        double advance=Math.hypot(player.getX()-lastX,player.getZ()-lastZ);
        if(advance>1.2)throw new AssertionError("Non-walking position discontinuity: "+advance);
        travelled+=advance;lastX=player.getX();lastZ=player.getZ();
        var target=points.get(pointIndex).getAsJsonArray();double dx=target.get(0).getAsDouble()-player.getX(),dz=target.get(2).getAsDouble()-player.getZ();
        while(Math.hypot(dx,dz)<.35&&pointIndex<points.size()-1){pointIndex++;target=points.get(pointIndex).getAsJsonArray();dx=target.get(0).getAsDouble()-player.getX();dz=target.get(2).getAsDouble()-player.getZ();}
        double reference=target.get(1).getAsDouble();
        if(Math.abs(player.getY()-reference)>2)throw new AssertionError("Walking height escaped source ground by more than2m");
        if(pointIndex==points.size()-1&&Math.hypot(dx,dz)<.35&&player.onGround()){
            var server=mc.getSingleplayerServer();var uuid=player.getUUID();
            var result=server.submit(()->{var p=server.getPlayerList().getPlayer(uuid);return new double[]{p.getX(),p.getY(),p.getZ(),p.onGround()?1:0,server.overworld().noCollision(p)?1:0,p.getAbilities().flying?1:0};}).join();
            if(Math.hypot(result[0]-target.get(0).getAsDouble(),result[2]-target.get(2).getAsDouble())>.6||result[3]!=1||result[4]!=1||result[5]!=0)throw new AssertionError("Server endpoint did not confirm walking arrival");
            if(travelled<current.get("minimumTravelMetres").getAsDouble())throw new AssertionError("Route shorter than expected");
            var row=new JsonObject();row.addProperty("label",current.get("label").getAsString());row.addProperty("travelledMetres",travelled);row.addProperty("movementTicks",movementTicks);row.addProperty("jumps",jumps);row.add("serverEndpoint",new Gson().toJsonTree(result));capture(mc,row,"end");completed.add(row);report("RUNNING: route completed");routeIndex++;started=false;moving=false;ticks=0;return;
        }
        if(movementTicks>20&&advance<.015)stalledTicks++;else stalledTicks=0;
        if(stalledTicks>100)throw new AssertionError("Forward input stalled for5seconds");
        if(++movementTicks>1200)throw new AssertionError("Route exceeded60seconds of walking");
        player.setYRot((float)Math.toDegrees(Math.atan2(-dx,dz)));player.setXRot(8);player.setSprinting(false);
        mc.options.keyUp.setDown(true);
        if(player.horizontalCollision&&player.onGround()){mc.options.keyJump.setDown(true);jumps++;}
        if(movementTicks%10==0){
            var row=new JsonObject();row.addProperty("route",routeIndex);row.addProperty("tick",movementTicks);row.addProperty("x",player.getX());row.addProperty("y",player.getY());row.addProperty("z",player.getZ());row.addProperty("onGround",player.onGround());row.addProperty("horizontalCollision",player.horizontalCollision);
            if(travelled>=nextCapture){capture(mc,row,Integer.toString((int)nextCapture));nextCapture+=5;}
            samples.add(row);report("RUNNING: continuous walking");
        }
    }
}
