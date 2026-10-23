package dev.realworldmc.client;
import net.minecraft.client.Minecraft;
import net.minecraft.world.phys.Vec3;
import org.joml.*;
import org.lwjgl.opengl.*;
import java.util.*;
import java.nio.file.*;
import com.google.gson.*;
import com.mojang.blaze3d.platform.GlStateManager;

public final class CampusShadowProbe {
    record Hit(int id,int part,float distance,Vector3f normal){}
    static List<MapTile> tiles;
    static Hit hit(Vec3 eye,Vector3f ray){
        Hit hit=new Hit(-1,-1,10000,new Vector3f());
        for(var tile:tiles){var data=tile.data;
            for(int pi=0;pi<data.parts.length;pi++){var v=data.parts[pi].vertices;
                for(int o=0;o<v.length;o+=15){
                    float t=Intersectionf.intersectRayTriangle((float)(eye.x-data.anchorX),(float)(eye.y-data.anchorY),(float)(eye.z-data.anchorZ),ray.x,ray.y,ray.z,v[o],v[o+1],v[o+2],v[o+5],v[o+6],v[o+7],v[o+10],v[o+11],v[o+12],1e-6f);
                    if(t>.005&&t<hit.distance){var n=new Vector3f(v[o+5]-v[o],v[o+6]-v[o+1],v[o+7]-v[o+2]).cross(v[o+10]-v[o],v[o+11]-v[o+1],v[o+12]-v[o+2]).normalize();if(n.dot(ray)>0)n.negate();hit=new Hit(data.id,pi,t,n);}
                }
            }
        }
        return hit;
    }
    public static void capture(Minecraft mc)throws Exception{
        var renderer=MapRenderer.INSTANCE;var lf=MapRenderer.class.getDeclaredField("loaded");lf.setAccessible(true);var df=MapRenderer.class.getDeclaredField("displayed");df.setAccessible(true);
        var loaded=(Map<Integer,MapTile>)lf.get(renderer);tiles=new ArrayList<>();for(int id:(List<Integer>)df.get(renderer)){var t=loaded.get(id);if(t!=null)tiles.add(t);}
        var mf=CampusShadows.class.getDeclaredField("matrix");mf.setAccessible(true);Matrix4f matrix=new Matrix4f((Matrix4f)mf.get(null));var inverse=new Matrix4f(matrix).invert();
        var tf=CampusShadows.class.getDeclaredField("target");tf.setAccessible(true);var target=(com.mojang.blaze3d.pipeline.TextureTarget)tf.get(null);
        int active=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);GlStateManager._activeTexture(GL13.GL_TEXTURE0);int texture=GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);
        var pixels=org.lwjgl.BufferUtils.createFloatBuffer(CampusShadows.SIZE*CampusShadows.SIZE);
        GlStateManager._bindTexture(target.getDepthTextureId());GL11.glGetTexImage(GL11.GL_TEXTURE_2D,0,GL11.GL_DEPTH_COMPONENT,GL11.GL_FLOAT,pixels);
        GlStateManager._bindTexture(texture);GlStateManager._activeTexture(active);
        var camera=mc.gameRenderer.getMainCamera();var eye=camera.getPosition();
        var fovMethod=net.minecraft.client.renderer.GameRenderer.class.getDeclaredMethod("getFov",net.minecraft.client.Camera.class,float.class,boolean.class);fovMethod.setAccessible(true);
        float fov=((Number)fovMethod.invoke(mc.gameRenderer,camera,1.0f,true)).floatValue();float tan=(float)java.lang.Math.tan(java.lang.Math.toRadians(fov)*.5);
        JsonArray result=new JsonArray();var sun=new Vector3f(-.5f,.8f,-.3f).normalize();
        for(float[] uv:new float[][]{{.1f,.55f},{.1f,.57f},{.12f,.6f},{.24f,.4f},{.25f,.41f},{.22f,.65f},{.56f,.4f},{.56f,.28f}}){
            var forward=new Vector3f(camera.getLookVector());var right=new Vector3f(forward).cross(0,1,0).normalize();var up=new Vector3f(right).cross(forward).normalize();
            var ray=new Vector3f(forward).add(right.mul((uv[0]*2-1)*tan*16/9)).add(up.mul((1-uv[1]*2)*tan)).normalize();
            var surface=hit(eye,ray);if(surface.id<0)continue;
            var point=eye.add(ray.x*surface.distance,ray.y*surface.distance,ray.z*surface.distance);
            var start=point.add(sun.x*.06,sun.y*.06,sun.z*.06);var caster=hit(start,sun);
            var q=matrix.transform(new Vector4f((float)point.x+surface.normal.x*.01f,(float)point.y+surface.normal.y*.01f,(float)point.z+surface.normal.z*.01f,1));q.div(q.w).mul(.5f).add(.5f,.5f,.5f,.5f);
            int ix=(int)(q.x*CampusShadows.SIZE),iy=(int)(q.y*CampusShadows.SIZE);
            if(ix<0||iy<0||ix>=CampusShadows.SIZE||iy>=CampusShadows.SIZE)continue;
            float depth=pixels.get(iy*CampusShadows.SIZE+ix);
            var occluder=inverse.transform(new Vector4f(((ix+.5f)/CampusShadows.SIZE)*2-1,((iy+.5f)/CampusShadows.SIZE)*2-1,depth*2-1,1));occluder.div(occluder.w);
            var p=new JsonObject();p.addProperty("u",uv[0]);p.addProperty("v",uv[1]);p.addProperty("surfaceTile",surface.id);p.addProperty("surfacePart",surface.part);p.addProperty("surface",point.toString());p.addProperty("sunCasterTile",caster.id);p.addProperty("sunCasterPart",caster.part);p.addProperty("sunCasterDistance",caster.distance);p.addProperty("surfaceDepth",q.z);p.addProperty("shadowDepth",depth);p.addProperty("shadowWorld",occluder.toString());result.add(p);
        }
        Files.writeString(Path.of("campus-shadow-probes.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
    }
}
