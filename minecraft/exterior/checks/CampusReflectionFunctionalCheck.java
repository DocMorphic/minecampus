package dev.realworldmc.client;

import com.google.gson.*;
import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.platform.GlStateManager;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.BlockState;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.lwjgl.opengl.*;
import java.nio.file.*;
import java.util.*;

/** Actual TNT fixtures and restoration, confined to the copied campus-check save. */
public final class CampusReflectionFunctionalCheck {
    private static final BlockPos GROUND=new BlockPos(44,64,-63);
    private static int phase,ticks,terrainChanged,newEdits;
    private static boolean preparationStarted;
    private static volatile boolean prepared;
    private static volatile Throwable failure;
    private static volatile boolean taskDone;
    private static Map<Long,BlockState> priorEdits;
    private static float[] baselineDepth;
    private static Matrix4f baselineMatrix;
    private static double glassAreaBefore;
    private static final JsonObject report=new JsonObject();
    public static void tick(Minecraft mc)throws Exception{
        if(failure!=null)throw new IllegalStateException("Reflection functional fixture",failure);
        if(!prepared){
            if(!preparationStarted){
                preparationStarted=true;
                if(!Path.of("").toAbsolutePath().getFileName().toString().equals("run-campus-check"))throw new AssertionError("Requires copied QA world");
                mc.getSingleplayerServer().execute(()->{
                    try{
                        var world=mc.getSingleplayerServer().overworld();var history=dev.realworldmc.MapEdits.storage(world);
                        report.addProperty("preexistingQaEditsResetForFixture",history.original.size());
                        var guard=dev.realworldmc.CampusCollision.class.getDeclaredField("updating");guard.setAccessible(true);var applying=(ThreadLocal<Boolean>)guard.get(null);applying.set(true);
                        try{for(var e:history.original.entrySet())world.setBlock(BlockPos.of(e.getKey()),e.getValue(),18);history.original.clear();}
                        finally{applying.set(false);}
                        history.setDirty();for(var player:world.players())dev.realworldmc.MapEdits.snapshot(player);prepared=true;
                    }catch(Throwable e){failure=e;}
                });
            }return;
        }
        if(++ticks<80)return;
        if(phase==0){
            if(!Path.of("").toAbsolutePath().getFileName().toString().equals("run-campus-check"))throw new AssertionError("Requires isolated QA directory");
            var source=CampusReflections.class.getProtectionDomain().getCodeSource().getLocation();
            if(!source.toString().endsWith(".jar"))throw new AssertionError("Requires packaged reflections");
            report.addProperty("rendererJar",Path.of(source.toURI()).getFileName().toString());
            if(CampusReflections.selected==null)throw new AssertionError("No reflective facade at fixture camera");
            baselineMatrix=matrix();baselineDepth=depth();capture(mc,"terrain-before");
            taskDone=false;mc.getSingleplayerServer().execute(()->{
                try{
                    var world=mc.getSingleplayerServer().overworld();
                    if(!dev.realworldmc.EarthBlocks.isMapBlock(world.getBlockState(GROUND)))throw new AssertionError("Terrain fixture is not intact");
                    priorEdits=new HashMap<>(dev.realworldmc.MapEdits.storage(world).original);
                    var tnt=new net.minecraft.world.entity.item.PrimedTnt(world,44.5,67,-62.5,null);tnt.setFuse(30);world.addFreshEntity(tnt);taskDone=true;
                }catch(Throwable e){failure=e;}
            });phase=1;ticks=0;return;
        }
        if(phase==1&&ticks>=140&&taskDone){
            if(!baselineMatrix.equals(matrix(),1e-5f))throw new AssertionError("TNT comparison camera/plane changed");
            terrainChanged=difference(baselineDepth,depth());
            if(terrainChanged<10)throw new AssertionError("TNT did not change enough reflected depth samples: "+terrainChanged);
            report.addProperty("terrainChangedReflectedDepthSamples",terrainChanged);capture(mc,"terrain-excavated");
            restore(mc,true);phase=2;ticks=0;return;
        }
        if(phase==2&&taskDone&&ticks>=120){
            int residual=difference(baselineDepth,depth());report.addProperty("terrainRestorationResidual",residual);report.addProperty("terrainTntEdits",newEdits);
            if(residual>32)throw new AssertionError("Reflected terrain did not restore: "+residual);
            capture(mc,"terrain-restored");glassAreaBefore=glassArea();report.addProperty("glassAreaBefore",glassAreaBefore);
            Vector3f centre=glassTarget();report.add("glassBlastCentre",new Gson().toJsonTree(new float[]{centre.x,centre.y,centre.z}));
            taskDone=false;mc.getSingleplayerServer().execute(()->{
                try{
                    var world=mc.getSingleplayerServer().overworld();boolean proxy=false;
                    var base=BlockPos.containing(centre.x,centre.y,centre.z);
                    for(var p:BlockPos.betweenClosed(base.offset(-2,-2,-2),base.offset(2,2,2)))if(dev.realworldmc.EarthBlocks.isMapBlock(world.getBlockState(p))){proxy=true;break;}
                    if(!proxy)throw new AssertionError("Glass TNT has no surveyed collision proxy nearby");
                    var tnt=new net.minecraft.world.entity.item.PrimedTnt(world,centre.x,centre.y,centre.z,null);tnt.setNoGravity(true);tnt.setFuse(30);world.addFreshEntity(tnt);taskDone=true;
                }catch(Throwable e){failure=e;}
            });phase=3;ticks=0;return;
        }
        if(phase==3&&taskDone&&ticks>=140){
            double after=glassArea();report.addProperty("glassAreaAfterTnt",after);
            if(after>glassAreaBefore-1)throw new AssertionError("Actual TNT did not remove glass area: "+glassAreaBefore+" -> "+after);
            capture(mc,"glass-excavated");restore(mc,false);phase=4;ticks=0;return;
        }
        if(phase==4&&taskDone&&ticks>=120){
            double restored=glassArea();report.addProperty("glassAreaRestored",restored);report.addProperty("glassTntEdits",newEdits);
            if(Math.abs(restored-glassAreaBefore)>.001)throw new AssertionError("Glass area not restored");
            int residual=difference(baselineDepth,depth());report.addProperty("finalReflectedDepthResidual",residual);
            if(residual>32)throw new AssertionError("Reflection did not recover after glass restoration: "+residual);
            verifyEmptyGlass();capture(mc,"glass-restored");
            report.addProperty("status","PASS: actual TNT changes reflected terrain and surviving facade glass; prior edits and native reflection recover after restoration");
            report.addProperty("depthDifferenceThreshold",.000001);report.addProperty("depthSamples",baselineDepth.length);
            phase=5;CampusReflectionLifecycleCheck.begin(mc,report);
        }
    }
    private static void restore(Minecraft mc,boolean ground){
        taskDone=false;mc.getSingleplayerServer().execute(()->{
            try{
                var world=mc.getSingleplayerServer().overworld();var history=dev.realworldmc.MapEdits.storage(world);
                newEdits=(int)history.original.keySet().stream().filter(k->!priorEdits.containsKey(k)).count();
                if(newEdits==0||ground&&!world.getBlockState(GROUND).isAir())throw new AssertionError("Actual explosion did not excavate its proxy");
                var guard=dev.realworldmc.CampusCollision.class.getDeclaredField("updating");guard.setAccessible(true);var applying=(ThreadLocal<Boolean>)guard.get(null);applying.set(true);
                try{for(var e:new HashMap<>(history.original).entrySet())if(!priorEdits.containsKey(e.getKey())){world.setBlock(BlockPos.of(e.getKey()),e.getValue(),18);history.original.remove(e.getKey());}}
                finally{applying.set(false);}
                history.setDirty();for(var player:world.players())dev.realworldmc.MapEdits.snapshot(player);
                if(!history.original.equals(priorEdits))throw new AssertionError("Existing edit history changed");taskDone=true;
            }catch(Throwable e){failure=e;}
        });
    }
    private static List<MapTile> glassTiles()throws Exception{
        var f=MapRenderer.class.getDeclaredField("loaded");f.setAccessible(true);var all=(Map<Integer,MapTile>)f.get(MapRenderer.INSTANCE);
        return all.values().stream().filter(t->t.data.id==1_000_000_100||t.data.id==1_000_000_101).toList();
    }
    private static double glassArea()throws Exception{
        double area=0;for(var t:glassTiles()){float[] v=t.reflectionGlass();if(v==null)continue;for(int i=0;i<v.length;i+=15){var a=point(t,v,i);var b=point(t,v,i+5);var c=point(t,v,i+10);area+=b.sub(a).cross(c.sub(a)).length()*.5;}}return area;
    }
    private static Vector3f point(MapTile t,float[] v,int i){return new Vector3f((float)(v[i]+t.data.anchorX),(float)(v[i+1]+t.data.anchorY),(float)(v[i+2]+t.data.anchorZ));}
    private static Vector3f glassTarget()throws Exception{
        Vector3f best=null;double distance=Double.POSITIVE_INFINITY;var plane=CampusReflections.selected.equation;
        for(var t:glassTiles()){var v=t.reflectionGlass();if(v==null)continue;for(int i=0;i<v.length;i+=15){var centre=point(t,v,i).add(point(t,v,i+5)).add(point(t,v,i+10)).div(3);
            if(Math.abs(plane.x*centre.x+plane.y*centre.y+plane.z*centre.z+plane.w)>.03)continue;
            double score=Math.pow(centre.y-66,2)+Math.pow(centre.z+62.5,2);if(score<distance){distance=score;best=centre;}
        }}if(best==null)throw new AssertionError("No glass fixture");return best;
    }
    private static void verifyEmptyGlass()throws Exception{
        var tile=glassTiles().getFirst();var d=tile.data;var b=tile.bounds;
        var cut=new dev.realworldmc.MeshCut.Box(b.minX-d.anchorX-1,b.minY-d.anchorY-1,b.minZ-d.anchorZ-1,b.maxX-d.anchorX+1,b.maxY-d.anchorY+1,b.maxZ-d.anchorZ+1);
        var empty=MapTile.withCuts(d,List.of(cut));
        try{
            var method=CampusReflections.class.getDeclaredMethod("panes",MapTile.class);method.setAccessible(true);
            int count=((List<?>)method.invoke(null,empty)).size();
            if(!empty.isEmpty(1)||empty.reflectionGlass().length!=0||count!=0)throw new AssertionError("Completely removed glass retained a reflection plane");
            report.addProperty("fullyCutGlassPlaneCount",count);
        }finally{empty.close();}
    }
    private static TextureTarget target()throws Exception{var f=CampusReflections.class.getDeclaredField("target");f.setAccessible(true);return (TextureTarget)f.get(null);}
    private static Matrix4f matrix()throws Exception{var f=CampusReflections.class.getDeclaredField("projectionToTexture");f.setAccessible(true);return new Matrix4f((Matrix4f)f.get(null));}
    private static float[] depth()throws Exception{
        var t=target();int prior=GL11.glGetInteger(GL30.GL_READ_FRAMEBUFFER_BINDING);var buffer=org.lwjgl.BufferUtils.createFloatBuffer(t.width*t.height);
        try{GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,t.frameBufferId);GL11.glReadPixels(0,0,t.width,t.height,GL11.GL_DEPTH_COMPONENT,GL11.GL_FLOAT,buffer);}finally{GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,prior);}
        float[] data=new float[buffer.remaining()];buffer.get(data);return data;
    }
    private static int difference(float[] a,float[] b){int count=0;for(int i=0;i<a.length;i++)if(Math.abs(a[i]-b[i])>.000001f)count++;return count;}
    private static void capture(Minecraft mc,String name)throws Exception{
        try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of("campus-reflection-functional-"+name+".png"));}
        CampusReflections.capture(Path.of("campus-reflection-functional-target-"+name+".png"));
        report.addProperty("latestCapture",name);Files.writeString(Path.of("campus-reflection-functional-progress.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
