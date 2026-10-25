import {woodShapes} from './wood-shapes.mjs';
/** Opt-in reconstructed solids use the same cell clipping as branches, while
 * preserving stone/plaster materials. Ground never enters this calculation. */
export function solidShapes(parts,grid){
  for(const p of parts)if(![4,6].includes(p.material))throw new RangeError('Unsupported fine solid material');
  const bounds=woodShapes(parts.flatMap(p=>p.triangles),grid),materials=new Map();
  // Later surface parts choose the material in shared cells; geometry always
  // includes the union of every part, so material choice cannot cut off a wall.
  for(const p of parts)for(const i of woodShapes(p.triangles,grid).keys())materials.set(i,p.material);
  return new Map([...bounds].map(([i,profile])=>[i,{profile,code:materials.get(i)}]));
}
