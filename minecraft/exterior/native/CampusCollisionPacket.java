package dev.realworldmc;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;

/** Strict MCWS parser; validation finishes before any world block is changed. */
public record CampusCollisionPacket(byte[] codes,int[] woodProfiles) {
    public static final int WOOD_PROFILE_COUNT=136*136;
    public static CampusCollisionPacket decode(byte[] bytes,int cells)throws IOException {
        if(cells<1||cells>65535||bytes.length<cells+8)throw new IOException("Truncated collision packet");
        var data=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);data.position(cells);
        if(data.get()!='M'||data.get()!='C'||data.get()!='W'||data.get()!='S')throw new IOException("Unknown collision packet version");
        int count=data.getInt();
        if(count<0||count>cells||bytes.length!=cells+8+count*4)throw new IOException("Invalid wood profile count");
        byte[] codes=Arrays.copyOf(bytes,cells);int[] profiles=new int[cells];Arrays.fill(profiles,-1);
        for(int i=0;i<count;i++){
            int index=data.getShort()&65535,profile=data.getShort()&65535;
            if(index>=cells||profile>=WOOD_PROFILE_COUNT||profiles[index]!=-1||(codes[index]&255)!=8)throw new IOException("Invalid wood collision entry");
            profiles[index]=profile;
        }
        return new CampusCollisionPacket(codes,profiles);
    }
}
