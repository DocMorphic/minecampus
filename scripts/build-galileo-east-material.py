#!/usr/bin/env python3
"""Generate identical bounded asphalt albedo in the normal and reflection passes."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'minecraft/exterior'
BEGIN='// BEGIN GENERATED GALILEO EAST MATERIAL\n';END='// END GENERATED GALILEO EAST MATERIAL'

def generate(spec):
    points=','.join('vec2(%.9f,%.9f)'%tuple(p) for p in spec['polygonMC'])
    polygon=spec['polygonMC'];winding=1 if sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(polygon,polygon[1:]+polygon[:1]))>0 else -1
    low,high=spec['heightRangeMC']
    return f'''// Bounded, inferred asphalt finish. Source: galileo-east-material.json.
// Restricted by the caller to terrain and the two ramp floor/collar parts.
const vec2 GalileoEastBoundary[4]=vec2[4]({points});
float galileoEastCoverage(vec3 position) {{
    if(position.y<{low:.1f}||position.y>{high:.1f})return 0.0;
    float signedDistance=1e6;
    for(int i=0;i<4;i++){{
        vec2 a=GalileoEastBoundary[i],b=GalileoEastBoundary[(i+1)%4];
        vec2 edge=b-a,p=position.xz-a;
        signedDistance=min(signedDistance,{winding:.1f}*(edge.x*p.y-edge.y*p.x)/length(edge));
    }}
    // Entirely inward blending keeps the neighbouring planting untouched.
    return smoothstep(0.0,max({spec['edgeBlendMetres']:.4f},fwidth(signedDistance)),signedDistance);
}}
vec3 galileoEastAlbedo(vec3 position) {{
    vec2 uv=position.xz/{spec['asphaltMetresPerRepeat']:.4f};
    return textureGrad(Sampler7,uv,dFdx(uv),dFdy(uv)).rgb*{spec['albedoMultiplier']:.4f};
}}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    spec=json.loads((SOURCE/'galileo-east-material.json').read_text());snippet=generate(spec)
    for name in ['campus_ground.fsh','campus_reflection.fsh']:
        target=SOURCE/'shaders'/name;text=target.read_text()
        if BEGIN in text:
            existing=text.split(BEGIN,1)[1].split(END,1)[0]
            if args.check:assert existing==snippet,name;continue
            text=text.split(BEGIN,1)[0]+BEGIN+snippet+END+text.split(END,1)[1]
        else:
            assert not args.check,'Missing generated material: '+name
            at=text.index('// BEGIN GENERATED REACTOR GROUND MAPPING')
            text=text[:at]+BEGIN+snippet+END+'\n'+text[at:]
        target.write_text(text)
    print('Galileo east shared material '+('verified' if args.check else 'generated'))
if __name__=='__main__':main()
