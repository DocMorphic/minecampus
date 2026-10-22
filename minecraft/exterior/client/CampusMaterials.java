package dev.realworldmc.client;

import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL12;
import org.lwjgl.opengl.GL30;

/** Shared, mipmapped CC0 micro-materials; no service/network dependency at runtime. */
public final class CampusMaterials {
    private static final String[] NAMES={"concrete_diff","concrete_normal","grass_diff","grass_normal"};
    private static final int[] prepared={-1,-1,-1,-1};
    private CampusMaterials(){}
    public static void bind(){
        var manager=Minecraft.getInstance().getTextureManager();
        for(int i=0;i<NAMES.length;i++){
            var location=ResourceLocation.fromNamespaceAndPath("realworldmc","textures/campus/"+NAMES[i]+".png");
            int id=manager.getTexture(location).getId();
            if(prepared[i]!=id){
                GlStateManager._bindTexture(id);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL12.GL_TEXTURE_MAX_LEVEL,10);
                GL30.glGenerateMipmap(GL11.GL_TEXTURE_2D);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MIN_FILTER,GL11.GL_LINEAR_MIPMAP_LINEAR);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MAG_FILTER,GL11.GL_LINEAR);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_S,GL11.GL_REPEAT);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_T,GL11.GL_REPEAT);
                prepared[i]=id;
            }
            RenderSystem.setShaderTexture(i+1,id);
        }
    }
}
