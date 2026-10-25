package dev.realworldmc;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;

/** Strict MCSP parser (with legacy wood-only MCWS support); validation finishes before any world block is changed. */
public record CampusCollisionPacket(byte[] codes,int[] profiles) {
    public static final int WOOD_PROFILE_COUNT=136*136;
    private static boolean validMaterial(int code,boolean legacy){return code==8||(!legacy&&(code==4||code==6));}
    public static CampusCollisionPacket decode(byte[] bytes,int cells)throws IOException {
        if(cells<1||cells>65535||bytes.length<cells+8)throw new IOException("Truncated collision packet");
        var data=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);data.position(cells);
        if(data.get()!='M'||data.get()!='C')throw new IOException("Unknown collision packet version");
        byte a=data.get(),b=data.get();boolean legacy=a=='W'&&b=='S';
        if(!legacy&&!(a=='S'&&b=='P'))throw new IOException("Unknown collision packet version");
        int count=data.getInt();
        if(count<0||count>cells||bytes.length!=cells+8+count*4)throw new IOException("Invalid profile count");
        byte[] codes=Arrays.copyOf(bytes,cells);int[] profiles=new int[cells];Arrays.fill(profiles,-1);
        for(int i=0;i<count;i++){
            int index=data.getShort()&65535,profile=data.getShort()&65535;
            if(index>=cells||profile>=WOOD_PROFILE_COUNT||profiles[index]!=-1||!validMaterial(codes[index]&255,legacy))throw new IOException("Invalid collision entry");
            profiles[index]=profile;
        }
        return new CampusCollisionPacket(codes,profiles);
    }
}
