package dev.realworldmc;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.level.material.MapColor;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Invisible, mineable wood with saved, network-synchronized horizontal bounds.
 * The vertical cell remains one Minecraft block. No block entities or ticking
 * entities are needed, and existing damage history stores the complete shape. */
public final class CampusWoodBlock extends EarthBlocks.MapBlock {
    // Minecraft stores transitions to every value of each property. Two axis
    // properties require 272 neighbours per state instead of 18,496.
    public static final IntegerProperty X=IntegerProperty.create("campus_wood_x",0,135);
    public static final IntegerProperty Z=IntegerProperty.create("campus_wood_z",0,135);
    private static final VoxelShape[] SHAPES=new VoxelShape[CampusCollisionPacket.WOOD_PROFILE_COUNT];
    static {
        int[][] intervals=new int[136][2];int n=0;
        for(int lo=0;lo<16;lo++)for(int hi=lo+1;hi<=16;hi++)intervals[n++]=new int[]{lo,hi};
        for(int x=0;x<136;x++)for(int z=0;z<136;z++)
            SHAPES[x*136+z]=Block.box(intervals[x][0],0,intervals[z][0],intervals[x][1],16,intervals[z][1]);
    }
    public static final CampusWoodBlock BLOCK=Registry.register(BuiltInRegistries.BLOCK,RealWorldMC.id("campus_wood"),new CampusWoodBlock());
    private CampusWoodBlock(){
        super(Properties.of().mapColor(MapColor.WOOD).strength(2,6).sound(SoundType.WOOD).noOcclusion().dynamicShape());
        registerDefaultState(stateDefinition.any().setValue(X,15).setValue(Z,15));
    }
    public static void init(){} // Called during the existing block registration phase.
    public static BlockState byProfile(int profile){
        if(profile<0||profile>=CampusCollisionPacket.WOOD_PROFILE_COUNT)throw new IllegalArgumentException("Invalid wood profile");
        return BLOCK.defaultBlockState().setValue(X,profile/136).setValue(Z,profile%136);
    }
    public static int profile(BlockState state){return state.getValue(X)*136+state.getValue(Z);}
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){super.createBlockStateDefinition(builder);builder.add(X,Z);}
    @Override protected VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return SHAPES[profile(state)];}
    @Override protected VoxelShape getCollisionShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return getShape(state,level,pos,context);}
}
