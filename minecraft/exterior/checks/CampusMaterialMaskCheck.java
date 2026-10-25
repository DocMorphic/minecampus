package dev.realworldmc.client;

import com.google.gson.*;
import com.mojang.blaze3d.platform.GlStateManager;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.lwjgl.opengl.*;

/** Optional source-control pixels read from an uploaded atlas in isolated QA. */
public final class CampusMaterialMaskCheck {
    private CampusMaterialMaskCheck() {}
    public static JsonArray check(Minecraft mc, JsonObject spec) {
        int texture=mc.getTextureManager().getTexture(ResourceLocation.parse(spec.get("texture").getAsString())).getId();
        var bounds=spec.getAsJsonArray("bounds");double left=bounds.get(0).getAsDouble(),bottom=bounds.get(1).getAsDouble(),right=bounds.get(2).getAsDouble(),top=bounds.get(3).getAsDouble();
        int size=spec.get("size").getAsInt();
        int previous=GL11.glGetInteger(GL30.GL_READ_FRAMEBUFFER_BINDING),fbo=GL30.glGenFramebuffers();
        var result=new JsonArray();
        try {
            GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,fbo);
            GL30.glFramebufferTexture2D(GL30.GL_READ_FRAMEBUFFER,GL30.GL_COLOR_ATTACHMENT0,GL11.GL_TEXTURE_2D,texture,0);
            if(GL30.glCheckFramebufferStatus(GL30.GL_READ_FRAMEBUFFER)!=GL30.GL_FRAMEBUFFER_COMPLETE)throw new AssertionError("Material atlas cannot be read from GPU");
            GL11.glReadBuffer(GL30.GL_COLOR_ATTACHMENT0);
            for(var entry:spec.getAsJsonArray("points")) {
                var point=entry.getAsJsonObject();double x=point.get("x").getAsDouble(),z=point.get("z").getAsDouble();
                int col=(int)Math.floor((x-left)/(right-left)*size),row=(int)Math.floor((top-z)/(top-bottom)*size);
                if(col<0||row<0||col>=size||row>=size)throw new AssertionError("Material control outside atlas");
                var bytes=org.lwjgl.BufferUtils.createByteBuffer(4);GL11.glReadPixels(col,row,1,1,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,bytes);
                var actual=new JsonArray();
                for(int i=0;i<4;i++) {int value=bytes.get(i)&255;actual.add(value);if(value!=point.getAsJsonArray("rgba").get(i).getAsInt())throw new AssertionError("Unexpected GPU material at "+x+", "+z);}
                var record=point.deepCopy();record.add("gpuRGBA",actual);result.add(record);
            }
        } finally {GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,previous);GL30.glDeleteFramebuffers(fbo);}
        return result;
    }
}
