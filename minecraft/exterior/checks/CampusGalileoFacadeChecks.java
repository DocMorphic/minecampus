package dev.realworldmc.client;

import com.google.gson.*;
import net.minecraft.client.Minecraft;
import org.joml.Vector3f;
import java.nio.file.*;

/** Samples the displayed native mesh; visual review is still required. */
public final class CampusGalileoFacadeChecks {
    public static void verify(Minecraft mc, java.util.Map<?,?> loaded, int stage) throws Exception {
        var source=MapRenderer.class.getProtectionDomain().getCodeSource().getLocation();
        if(!source.toString().endsWith(".jar"))throw new AssertionError("Facade review requires packaged renderer");
        var displayedField=MapRenderer.class.getDeclaredField("displayed");displayedField.setAccessible(true);
        var displayed=(java.util.List<?>)displayedField.get(MapRenderer.INSTANCE);
        var camera=mc.gameRenderer.getMainCamera();var eye=camera.getPosition();
        var method=net.minecraft.client.renderer.GameRenderer.class.getDeclaredMethod("getFov",net.minecraft.client.Camera.class,float.class,boolean.class);method.setAccessible(true);
        float tangent=(float)Math.tan(Math.toRadians(((Number)method.invoke(mc.gameRenderer,camera,1f,true)).doubleValue())*.5);
        var forward=new Vector3f(camera.getLookVector());var right=new Vector3f(forward).cross(0,1,0).normalize();var up=new Vector3f(right).cross(forward).normalize();
        int metal=0,glass=0,roof=0;var picks=new JsonArray();
        for(float v:new float[]{.2f,.3f,.4f,.5f,.6f})for(float u:new float[]{.2f,.3f,.4f,.5f,.6f,.7f,.8f}){
            var ray=new Vector3f(forward).fma((2*u-1)*tangent*mc.getWindow().getWidth()/mc.getWindow().getHeight(),right).fma((1-2*v)*tangent,up).normalize();
            float distance=1000;int hit=-1,part=-1;
            for(var value:loaded.values()){
                var tile=(MapTile)value;var data=tile.data;
                if(!displayed.contains(data.id)||data.id>=1_000_010_000&&data.id<1_000_020_000)continue;
                var bounds=tile.bounds;
                if(!org.joml.Intersectiond.testRayAab(eye.x,eye.y,eye.z,ray.x,ray.y,ray.z,bounds.minX,bounds.minY,bounds.minZ,bounds.maxX,bounds.maxY,bounds.maxZ))continue;
                float x=(float)(eye.x-data.anchorX),y=(float)(eye.y-data.anchorY),z=(float)(eye.z-data.anchorZ);
                for(int p=0;p<data.parts.length;p++){
                    var vertices=data.parts[p].vertices;
                    for(int i=0;i<vertices.length;i+=15){
                        float t=org.joml.Intersectionf.intersectRayTriangle(x,y,z,ray.x,ray.y,ray.z,vertices[i],vertices[i+1],vertices[i+2],vertices[i+5],vertices[i+6],vertices[i+7],vertices[i+10],vertices[i+11],vertices[i+12],1e-6f);
                        if(t>0&&t<distance){distance=t;hit=data.id;part=p;}
                    }
                }
            }
            if(hit==1_000_000_100||hit==1_000_000_101){if(part==0)metal++;if(part==1)glass++;if(part==3)roof++;}
            var pick=new JsonObject();pick.addProperty("u",u);pick.addProperty("v",v);pick.addProperty("tile",hit);pick.addProperty("part",part);pick.addProperty("distance",distance);picks.add(pick);
        }
        var report=new JsonObject();report.addProperty("stage",stage);report.addProperty("rendererJar",Path.of(source.toURI()).getFileName().toString());report.addProperty("metalHits",metal);report.addProperty("glassHits",glass);report.addProperty("roofHits",roof);report.add("structuralRaysIgnoringFoliage",picks);
        Files.writeString(Path.of("campus-galileo-facade-rays-"+stage+".json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        if(stage==45?roof==0:metal==0||glass==0)throw new AssertionError("Facade sampling misses required material parts at stage "+stage+": "+metal+", "+glass+", "+roof);
        Files.writeString(Path.of("campus-galileo-facade-"+stage+"-result.txt"),"PASS: displayed packaged Galileo facade has sampled metal/glass or preserved aerial roof geometry");
    }
}
