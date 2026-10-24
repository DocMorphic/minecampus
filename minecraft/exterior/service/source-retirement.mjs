// Clip only explicitly reconstructed source volumes, including tree overhangs
// outside the land surface. Preserve source UVs, colours and unrelated geometry.
import {surfaceBoundaryClipper} from './supplemental-surfaces.mjs';

export function prepareSourceRetirement(entries = []) {
  if (!entries.length) return bytes => bytes;
  const clipper = surfaceBoundaryClipper(entries);
  return (bytes, shift=0) => {
    const input = Buffer.isBuffer(bytes) ? bytes : Buffer.from(bytes);
    if (input.toString('ascii',0,4)!=='ECT1') throw Error('Unsupported source mesh');
    const count=input.readInt32LE(4),anchor=[8,16,24].map(i=>input.readDoubleLE(i));
    const parts=[input.subarray(0,32)]; let offset=32;
    for(let part=0;part<count;part++){
      const vertices=input.readInt32LE(offset),w=input.readInt32LE(offset+4),h=input.readInt32LE(offset+8);
      const header=Buffer.from(input.subarray(offset,offset+16));offset+=16;
      const fragments=[];
      for(let index=0;index<vertices;index+=3){
        const triangle=[0,1,2].map(i=>{
          const at=offset+(index+i)*20;
          return [input.readFloatLE(at)+anchor[0],input.readFloatLE(at+4)+anchor[1]-shift,input.readFloatLE(at+8)+anchor[2],input.readFloatLE(at+12),input.readFloatLE(at+16)];
        });
        fragments.push(...clipper.outsideFragments(triangle));
      }
      offset+=vertices*20;
      header.writeInt32LE(fragments.length*3,0);
      const geometry=Buffer.allocUnsafe(fragments.length*60);let write=0;
      for(const triangle of fragments)for(const p of triangle){
        [p[0]-anchor[0],p[1]+shift-anchor[1],p[2]-anchor[2],p[3],p[4]].forEach((v,i)=>geometry.writeFloatLE(v,write+i*4));write+=20;
      }
      parts.push(header,geometry,input.subarray(offset,offset+w*h*4));offset+=w*h*4;
    }
    if(offset!==input.length)throw Error('Invalid source mesh length');
    return Buffer.concat(parts);
  };
}
