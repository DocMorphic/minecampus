import test from 'node:test';
import assert from 'node:assert/strict';
import {surveyedWaterGround} from './water-survey.mjs';

function feature(offset=0) {
  return {surveyGround:{heightOffset:offset,
    rings:[{ring:[[1,0],[3,0],[3,4],[1,4]],holes:[[[1.9,1.9],[2.9,1.9],[2.9,2.9],[1.9,2.9]]]}],
    terrainGuide:{width:3,height:3,points:Array.from({length:9},(_,i)=>[(i%3)*2,61.35,Math.floor(i/3)*2])}}};
}
test('surveyed channel ground rejects canopy height without changing unstudied or holed columns',()=>{
  const input=new Float64Array(16).fill(75);
  const output=surveyedWaterGround([feature()],input,0,0,4);
  assert.equal(output[1],60);
  assert.equal(output[2],60);
  assert.equal(output[0],75);
  assert.equal(output[3],75);
  assert.equal(output[2*4+2],75);
  assert.deepEqual(input,new Float64Array(16).fill(75));
});
test('alternate local altitude datum shifts water input, leaving original features immutable',()=>{
  const f=feature(3),input=new Float64Array(16).fill(75);
  assert.equal(surveyedWaterGround([f],input,0,0,4)[1],63);
  assert.equal(f.surveyGround.terrainGuide.points[0][1],61.35);
});
test('absent or disjoint river surveys preserve upstream ground samples',()=>{
  const input=new Float64Array(16).fill(75);
  assert.strictEqual(surveyedWaterGround([],input,0,0,4),input);
  assert.deepEqual(surveyedWaterGround([feature()],input,100,100,4),input);
});
