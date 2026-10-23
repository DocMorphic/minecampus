package dev.realworldmc.client;

import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL12;
import org.lwjgl.opengl.GL30;
import org.lwjgl.opengl.GL;
import org.lwjgl.opengl.EXTTextureFilterAnisotropic;

/** Shared, mipmapped CC0 micro-materials; no service/network dependency at runtime. */
public final class CampusMaterials {
    private static final String[] NAMES={"concrete_diff","concrete_normal","grass_diff","grass_normal","ground_surfaces","brick_normal"};
    private static final int[] prepared={-1,-1,-1,-1,-1,-1};
    private CampusMaterials(){}
    public static void bind(){
        var manager=Minecraft.getInstance().getTextureManager();
        for(int i=0;i<NAMES.length;i++){
            var location=ResourceLocation.fromNamespaceAndPath("realworldmc","textures/campus/"+NAMES[i]+".png");
            int id=manager.getTexture(location).getId();
            if(prepared[i]!=id){
                GlStateManager._bindTexture(id);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL12.GL_TEXTURE_MAX_LEVEL,i==4?12:10);
                GL30.glGenerateMipmap(GL11.GL_TEXTURE_2D);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MIN_FILTER,GL11.GL_LINEAR_MIPMAP_LINEAR);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MAG_FILTER,GL11.GL_LINEAR);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_S,i==4?GL12.GL_CLAMP_TO_EDGE:GL11.GL_REPEAT);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_T,i==4?GL12.GL_CLAMP_TO_EDGE:GL11.GL_REPEAT);
                if(GL.getCapabilities().GL_EXT_texture_filter_anisotropic){
                    float maximum=GL11.glGetFloat(EXTTextureFilterAnisotropic.GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT);
                    GL11.glTexParameterf(GL11.GL_TEXTURE_2D,EXTTextureFilterAnisotropic.GL_TEXTURE_MAX_ANISOTROPY_EXT,Math.min(16f,maximum));
                }
                prepared[i]=id;
            }
            RenderSystem.setShaderTexture(i+1,id);
        }
    }
}
