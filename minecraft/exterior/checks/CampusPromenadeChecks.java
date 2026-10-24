package dev.realworldmc.client;

import com.google.gson.*;
import com.mojang.blaze3d.platform.GlStateManager;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.lwjgl.opengl.*;
import java.nio.file.*;

/** Path and facade-seam controls, read back from the active GPU material mask. */
public final class CampusPromenadeChecks {
    public static void verify(Minecraft mc,java.util.Map<?,?> loaded)throws Exception{
        double[][] points={{30275349,5.515,15.875},{32458178,62.714,-23.075},{386192514,60.228,-90.700},{617369303,35.228,-76.411},{32458178,82.148982,-97.193730},{32458178,81.967341,-96.261060},{32458178,81.596075,-94.214627}};
        verifyControls(mc,loaded,points,"promenade","four mapped path controls and three facade-seam controls");
    }
    public static void verifyControls(Minecraft mc,java.util.Map<?,?> loaded,double[][] points,String name,String description)throws Exception{
        var location=ResourceLocation.fromNamespaceAndPath("realworldmc","textures/campus/ground_surfaces.png");
        int texture=mc.getTextureManager().getTexture(location).getId();
        if(com.mojang.blaze3d.systems.RenderSystem.getShaderTexture(5)!=texture)throw new AssertionError("Promenade mask is not bound to the campus material sampler");
        var source=MapRenderer.class.getProtectionDomain().getCodeSource().getLocation();
        if(!source.toString().endsWith(".jar"))throw new AssertionError("Promenade review requires the packaged renderer");
        int previous=GL11.glGetInteger(GL30.GL_READ_FRAMEBUFFER_BINDING),fbo=GL30.glGenFramebuffers();
        var report=new JsonArray();
        try{
            GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,fbo);
            GL30.glFramebufferTexture2D(GL30.GL_READ_FRAMEBUFFER,GL30.GL_COLOR_ATTACHMENT0,GL11.GL_TEXTURE_2D,texture,0);
            if(GL30.glCheckFramebufferStatus(GL30.GL_READ_FRAMEBUFFER)!=GL30.GL_FRAMEBUFFER_COMPLETE)throw new AssertionError("Material mask cannot be read from GPU");
            GL11.glReadBuffer(GL30.GL_COLOR_ATTACHMENT0);
            for(var point:points){
                int x=(int)((point[1]+352)/672*4096),y=(int)((256-point[2])/672*4096);
                var pixel=org.lwjgl.BufferUtils.createByteBuffer(4);GL11.glReadPixels(x,y,1,1,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,pixel);
                if((pixel.get(0)&255)!=0||(pixel.get(1)&255)!=0||(pixel.get(2)&255)!=255||(pixel.get(3)&255)!=255)throw new AssertionError("GPU promenade mask misses way "+(long)point[0]);
                float distance=1000;int hit=-1;
                for(var item:loaded.values()){
                    var tile=(MapTile)item;var d=tile.data;if(d.id<1_000_000_000||d.id>=1_000_000_036)continue;
                    for(var part:d.parts){var v=part.vertices;for(int o=0;o<v.length;o+=15){
                        float t=org.joml.Intersectionf.intersectRayTriangle((float)(point[1]-d.anchorX),(float)(100-d.anchorY),(float)(point[2]-d.anchorZ),0,-1,0,v[o],v[o+1],v[o+2],v[o+5],v[o+6],v[o+7],v[o+10],v[o+11],v[o+12],1e-6f);
                        if(t>0&&t<distance){distance=t;hit=d.id;}
                    }}
                }
                if(hit<0||distance<30||distance>40)throw new AssertionError("Promenade control has no surveyed ground: "+(long)point[0]);
                var record=new JsonObject();record.addProperty("osmWay",(long)point[0]);record.addProperty("x",point[1]);record.addProperty("z",point[2]);record.addProperty("groundY",100-distance);record.addProperty("terrainTile",hit);record.addProperty("gpuMaskRGBA","0,0,255,255");report.add(record);
            }
        }finally{GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,previous);GL30.glDeleteFramebuffers(fbo);}
        var result=new JsonObject();result.addProperty("rendererJar",Path.of(source.toURI()).getFileName().toString());result.add("controls",report);
        Files.writeString(Path.of("campus-"+name+"-controls.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        Files.writeString(Path.of("campus-"+name+"-result.txt"),"PASS: "+description+" reach loaded surveyed ground and the active GPU asphalt mask");
    }
}
