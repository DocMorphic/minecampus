import {WOOD_PROFILE_COUNT} from './wood-shapes.mjs';
/** Versioned sparse wood profiles after the unchanged voxel material bytes. */
export function encodeCollisionPacket(codes,profiles){
  if(!(codes instanceof Uint8Array)||codes.length>65535)throw new RangeError('Invalid collision grid');
  const output=Buffer.alloc(codes.length+8+profiles.size*4);output.set(codes);output.write('MCWS',codes.length);output.writeUInt32LE(profiles.size,codes.length+4);
  let offset=codes.length+8;
  for(const [index,profile]of profiles){
    if(!Number.isInteger(index)||index<0||index>=codes.length||codes[index]!==8||!Number.isInteger(profile)||profile<0||profile>=WOOD_PROFILE_COUNT)throw new RangeError('Invalid wood collision profile');
    output.writeUInt16LE(index,offset);output.writeUInt16LE(profile,offset+2);offset+=4;
  }
  return output;
}
