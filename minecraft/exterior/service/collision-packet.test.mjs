import test from 'node:test';
import assert from 'node:assert/strict';
import {encodeCollisionPacket} from './collision-packet.mjs';
test('sparse profiles preserve material bytes and encode large indices without truncation',()=>{
 const codes=new Uint8Array(24576).fill(255);codes[2]=8;codes[24000]=8;codes[100]=23;codes[7]=4;codes[9]=6;
 const packet=encodeCollisionPacket(codes,new Map([[2,18495],[24000,0],[7,540],[9,134]]));
 assert.deepEqual(packet.subarray(0,codes.length),Buffer.from(codes));assert.equal(packet.subarray(codes.length,codes.length+4).toString(),'MCSP');
 assert.equal(packet.readUInt32LE(codes.length+4),4);assert.equal(packet.readUInt16LE(codes.length+8),2);assert.equal(packet.readUInt16LE(codes.length+10),18495);assert.equal(packet.readUInt16LE(codes.length+12),24000);
 codes[0]=0;assert.equal(packet[0],255);
});
test('profile packets cannot override water, terrain, unknown cells or invalid entries',()=>{
 for(const code of [0,3,23,45,255])assert.throws(()=>encodeCollisionPacket(Uint8Array.of(code),new Map([[0,1]])),RangeError);
 for(const [index,profile]of [[1,0],[-1,0],[0,18496],[0,-1],[0,.5]])assert.throws(()=>encodeCollisionPacket(Uint8Array.of(8),new Map([[index,profile]])),RangeError);
 assert.equal(encodeCollisionPacket(Uint8Array.of(255),new Map()).length,9);
});
