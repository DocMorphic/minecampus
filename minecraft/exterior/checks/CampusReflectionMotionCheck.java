package dev.realworldmc.client;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import org.joml.Matrix4f;
import org.joml.Vector4f;
import org.lwjgl.opengl.GL20;

/** Reads the actual material GPU matrix after each moving-camera frame. */
public final class CampusReflectionMotionCheck implements ClientModInitializer {
    public static boolean active;
    public static long checked,lastFrame;
    public static double travelled;
    private static net.minecraft.world.phys.Vec3 prior;
    @Override public void onInitializeClient(){
        WorldRenderEvents.LAST.register(context->{
            if(!active)return;
            try{
                var eye=context.camera().getPosition();var selected=CampusReflections.selected;
                if(selected==null||CampusReflections.frames==lastFrame||eye.distanceTo(CampusReflections.frameCamera)>1e-8)
                    throw new AssertionError("Reflection did not use this frame's camera");
                var plane=new Vector4f(selected.equation);
                var reflection=new Matrix4f().reflection(plane.x,plane.y,plane.z,plane.w);
                var expected=new Matrix4f(context.projectionMatrix()).mul(new Matrix4f(context.positionMatrix()).translate(-(float)eye.x,-(float)eye.y,-(float)eye.z).mul(reflection));
                var f=MapRenderer.class.getDeclaredField("campusGroundShader");f.setAccessible(true);
                var shader=(net.minecraft.client.renderer.ShaderInstance)f.get(null);float[] data=new float[16];
                GL20.glGetUniformfv(shader.getId(),GL20.glGetUniformLocation(shader.getId(),"PlanarMatrix"),data);
                if(!expected.equals(new Matrix4f().set(data),.001f))throw new AssertionError("GPU reflection matrix lags the moving camera");
                if(prior!=null)travelled+=eye.distanceTo(prior);prior=eye;
                lastFrame=CampusReflections.frames;checked++;
            }catch(ReflectiveOperationException error){throw new IllegalStateException(error);}
        });
    }
}
