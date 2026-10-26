package dev.realworldmc;

import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.saveddata.SavedData;
import java.time.Duration;
import java.util.HashSet;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Executors;

/** Aligns existing proxy blocks with the surveyed exterior, retaining explicit
 * damage records and all ordinary player-built blocks. Requests contain only
 * local mesh data, not additional provider downloads. */
public final class CampusCollision {
    private static final int MIN_Y=48, HEIGHT=96;
    private static final Set<Long> inFlight=new HashSet<>();
    private record LightingResync(ServerLevel level,LevelChunk chunk,int afterTick){}
    private static final Map<Long,LightingResync> lightingResync=new HashMap<>();
    private static final ThreadLocal<Boolean> updating=ThreadLocal.withInitial(()->false);
    private static final java.util.concurrent.ExecutorService IO=Executors.newFixedThreadPool(2,r->{var t=new Thread(r,"Minecampus collision alignment");t.setDaemon(true);return t;});
    private static int epoch;
    public static long changedBlocks;
    public static long lightingResyncPackets;
    private static boolean unavailable;
    private CampusCollision(){}
    public static boolean applying(){return updating.get();}
    public static void register(){
        ServerTickEvents.END_SERVER_TICK.register(CampusCollision::tick);
        ServerLifecycleEvents.SERVER_STOPPED.register(server->{epoch++;inFlight.clear();lightingResync.clear();unavailable=false;changedBlocks=0;lightingResyncPackets=0;});
    }
    private static Storage storage(ServerLevel level){return level.getDataStorage().computeIfAbsent(new SavedData.Factory<>(Storage::new,Storage::load,null),"minecampus_exterior_collision_v94");}
    private static void tick(MinecraftServer server){
        flushLighting(server);
        if(unavailable||server.getTickCount()%10!=0)return;
        var level=server.overworld();
        if(!(level.getChunkSource().getGenerator() instanceof EarthChunkGenerator))return;
        for(var player:level.players()){
            var p=player.chunkPosition();
            // Complete the nearest chunks before loading terrain the player may never visit.
            for(int radius=0;radius<=2;radius++)for(int dx=-radius;dx<=radius;dx++)for(int dz=-radius;dz<=radius;dz++){
                if(Math.max(Math.abs(dx),Math.abs(dz))!=radius)continue;
                var chunk=level.getChunkSource().getChunkNow(p.x+dx,p.z+dz);
                if(chunk!=null)queue(level,chunk);
            }
        }
    }
    private static void queue(ServerLevel level,LevelChunk chunk){
        long key=chunk.getPos().toLong();if(inFlight.size()>=4||inFlight.contains(key)||storage(level).done.contains(key))return;
        var pos=chunk.getPos();var region=EarthRegions.at(pos.getMiddleBlockX(),pos.getMiddleBlockZ());
        if(region==null||Math.abs(region.latitude()-48.265)>1e-7||Math.abs(region.longitude()-11.671)>1e-7||!Double.isFinite(region.groundHeight()))return;
        int cx=pos.x-region.offsetX()/16,cz=pos.z-region.offsetZ()/16;
        // Physics I, P1 and the campus woodland extend east of the original terrain rectangle. The service
        // still returns 255 outside its explicit, neighbour-safe survey patches.
        if(cx< -22||cx>41||cz< -35||cz>16)return;
        int generation=epoch;inFlight.add(key);
        IO.execute(()->{
            try{
                String q="/campus/collision?"+ServiceClient.originQuery(region.latitude(),region.longitude(),region.groundHeight())+"&cx="+cx+"&cz="+cz+"&minY="+MIN_Y+"&height="+HEIGHT+"&wood=1";
                CampusCollisionPacket packet=CampusCollisionPacket.decode(ServiceClient.getBytes(q,Duration.ofSeconds(30)),16*16*HEIGHT);
                level.getServer().execute(()->{
                    try{if(generation==epoch&&level.getChunkSource().getChunkNow(pos.x,pos.z)==chunk)apply(level,chunk,packet);}
                    finally{inFlight.remove(key);}
                });
            }catch(Exception e){
                level.getServer().execute(()->{inFlight.remove(key);if(generation!=epoch)return;
                    if(e instanceof ServiceClient.ServiceException se&&se.status==404)unavailable=true;
                    else RealWorldMC.LOGGER.warn("Campus collision alignment will retry: {}",e.getMessage());
                });
            }
        });
    }
    private static void apply(ServerLevel level,LevelChunk chunk,CampusCollisionPacket packet){
        byte[] codes=packet.codes();int[] profiles=packet.profiles();
        var history=MapEdits.storage(level);var base=chunk.getPos();var position=new BlockPos.MutableBlockPos();int changes=0;
        updating.set(true);
        try{
            for(int y=0;y<HEIGHT;y++)for(int z=0;z<16;z++)for(int x=0;x<16;x++){
                int index=(y*16+z)*16+x,code=codes[index]&255;if(code==255)continue;
                position.set(base.getMinBlockX()+x,MIN_Y+y,base.getMinBlockZ()+z);
                if(history.original.containsKey(position.asLong()))continue;
                var before=level.getBlockState(position);
                if(!before.isAir()&&!EarthBlocks.isMapBlock(before))continue;
                var after=profiles[index]>=0?(code==8?CampusWoodBlock.byProfile(profiles[index]):CampusSolidBlock.byProfile(code,profiles[index])):EarthBlocks.byCode(code);
                if(before!=after&&level.setBlock(position,after,Block.UPDATE_CLIENTS|Block.UPDATE_KNOWN_SHAPE))changes++;
            }
        }finally{updating.set(false);}
        var saved=storage(level);saved.done.add(base.toLong());saved.setDirty();changedBlocks+=changes;
        RealWorldMC.LOGGER.info("Campus collision aligned chunk {}, {}: {} proxy blocks; player edits preserved",base.x,base.z,changes);
        if(changes>0)resyncLighting(level,chunk);
    }
    /** Bulk proxy changes can leave client light data behind the server. Send
     * the authoritative light after queued work and block broadcasts finish.
     * This changes no blocks and does not force-load neighbouring chunks. */
    private static void resyncLighting(ServerLevel level,LevelChunk chunk){
        int generation=epoch;var pos=chunk.getPos();var source=level.getChunkSource();
        source.getLightEngine().waitForPendingTasks(pos.x,pos.z).thenRun(()->level.getServer().execute(()->{
            if(generation!=epoch||source.getChunkNow(pos.x,pos.z)!=chunk)return;
            // Adjacent sections also receive light from the changed boundary.
            // Coalesce nearby migrations and leave a tick for block broadcasts.
            for(int dx=-1;dx<=1;dx++)for(int dz=-1;dz<=1;dz++){
                var neighbour=source.getChunkNow(pos.x+dx,pos.z+dz);
                if(neighbour!=null)lightingResync.put(neighbour.getPos().toLong(),new LightingResync(level,neighbour,level.getServer().getTickCount()+20));
            }
        })).exceptionally(error->{RealWorldMC.LOGGER.warn("Campus lighting synchronization failed",error);return null;});
    }
    private static void flushLighting(MinecraftServer server){
        var iterator=lightingResync.values().iterator();
        while(iterator.hasNext()){
            var pending=iterator.next();if(server.getTickCount()<pending.afterTick())continue;
            iterator.remove();var source=pending.level().getChunkSource();var pos=pending.chunk().getPos();
            if(source.getChunkNow(pos.x,pos.z)!=pending.chunk())continue;
            var players=source.chunkMap.getPlayers(pos,false);if(players.isEmpty())continue;
            var packet=new net.minecraft.network.protocol.game.ClientboundLightUpdatePacket(pos,source.getLightEngine(),null,null);
            for(var player:players){player.connection.send(packet);lightingResyncPackets++;}
        }
    }
    public static boolean aligned(ServerLevel level,int cx,int cz){return storage(level).done.contains(net.minecraft.world.level.ChunkPos.asLong(cx,cz));}
    public static final class Storage extends SavedData {
        final Set<Long> done=new HashSet<>();
        static Storage load(CompoundTag tag,HolderLookup.Provider provider){var s=new Storage();for(long key:tag.getLongArray("chunks"))s.done.add(key);return s;}
        @Override public CompoundTag save(CompoundTag tag,HolderLookup.Provider provider){tag.putLongArray("chunks",done.stream().mapToLong(Long::longValue).toArray());return tag;}
    }
}
