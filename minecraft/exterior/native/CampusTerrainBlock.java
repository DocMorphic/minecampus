package dev.realworldmc;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Invisible surveyed supports; existing map block IDs default to full height. */
public final class CampusTerrainBlock extends EarthBlocks.MapBlock {
    public static final IntegerProperty HEIGHT=IntegerProperty.create("campus_height",1,16);
    private static final VoxelShape[] SHAPES=new VoxelShape[16];
    static {for(int i=0;i<16;i++)SHAPES[i]=Block.box(0,0,0,16,i+1,16);}
    public CampusTerrainBlock(Properties properties){
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(HEIGHT,16));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){
        super.createBlockStateDefinition(builder);
        builder.add(HEIGHT);
    }
    @Override protected VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){
        return SHAPES[state.getValue(HEIGHT)-1];
    }
    @Override protected VoxelShape getCollisionShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){
        return getShape(state,level,pos,context);
    }
}
