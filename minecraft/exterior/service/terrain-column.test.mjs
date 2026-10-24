import test from 'node:test';
import assert from 'node:assert/strict';
import {terrainColumnHeight} from './terrain-column.mjs';

test('eastern roadside support uses the measured cell centre, not a raised corner',()=>{
  const triangle=[492.0402526855469,65.1030044555664,-221.57643127441406,
    493.0048828125,65.47869110107422,-220.54225158691406,
    493.0396728515625,65.54765319824219,-221.54164123535156];
  const height=terrainColumnHeight(triangle,492,-222);
  assert.ok(Math.abs(height-65.30431917930173)<1e-8);
  assert.equal(Math.floor(height-.5)+1,65);
  assert.equal(terrainColumnHeight(triangle,491,-222),null);
});

test('heightfield sampling preserves both triangle windings, seams and negative coordinates',()=>{
  const a=[-2,10,-2,2,12,-2,2,14,2],b=[-2,10,-2,2,14,2,-2,12,2];
  for(let z=-2;z<2;z++)for(let x=-2;x<2;x++){
    const hits=[a,b].map(t=>terrainColumnHeight(t,x,z)).filter(v=>v!==null);
    assert.ok(hits.length>=1);
    for(const h of hits)assert.ok(Math.abs(h-(12+.5*(x+.5)+.5*(z+.5)))<1e-10);
  }
  assert.equal(terrainColumnHeight(a,2,0),null);
  assert.equal(terrainColumnHeight([0,0,0,0,1,0,0,1,1],0,0),null);
  assert.equal(terrainColumnHeight([...b.slice(6),...b.slice(3,6),...b.slice(0,3)],-1,0),terrainColumnHeight(b,-1,0));
});
