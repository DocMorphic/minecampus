#!/usr/bin/env python3
"""Generate bounded courtyard paving in both ground and reflection shaders."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'minecraft/exterior'
BEGIN = '// BEGIN GENERATED LOW BUILDING PAVING\n'
END = '// END GENERATED LOW BUILDING PAVING'


def generate(spec):
    parts = ['// DOP20 patio/path interpretation; hidden edges, slab size and finish are inferred.\n']
    for index, region in enumerate(spec['regions']):
        points = region['polygonMC']
        count = len(points)
        values = ','.join('vec2(%.9f,%.9f)' % tuple(p) for p in points)
        parts.append(f'''float courtyardPatch{index}(vec2 p) {{
    const vec2 boundary[{count}]=vec2[{count}]({values});
    bool inside=false;float edgeDistance=1e6;
    for(int i=0;i<{count};i++) {{
        vec2 a=boundary[i],b=boundary[(i+1)%{count}],v=b-a;
        edgeDistance=min(edgeDistance,length(p-a-v*clamp(dot(p-a,v)/dot(v,v),0.0,1.0)));
        if((a.y>p.y)!=(b.y>p.y)) {{
            float crossX=a.x+(p.y-a.y)*(b.x-a.x)/(b.y-a.y);
            if(p.x<crossX)inside=!inside;
        }}
    }}
    return inside?smoothstep(0.0,{spec['edgeBlendMetres']:.4f},edgeDistance):0.0;
}}
''')
    all_points = [p for r in spec['regions'] for p in r['polygonMC']]
    low, high = spec['heightRangeMC']
    calls = ','.join('courtyardPatch%d(position.xz)' % i for i in range(len(spec['regions'])))
    # Explicit max nesting supports an arbitrary number of disjoint patches.
    expression = '0.0'
    for call in calls.split(','):
        expression = f'max({expression},{call})'
    # The building axes are defined by its survey frame, not screen coordinates.
    dx, dz = spec['pavingAxisMC']
    parts.append(f'''float courtyardPavingCoverage(vec3 position) {{
    if(position.y<{low:.4f}||position.y>{high:.4f}
       ||position.x<{min(p[0] for p in all_points):.9f}||position.x>{max(p[0] for p in all_points):.9f}
       ||position.z<{min(p[1] for p in all_points):.9f}||position.z>{max(p[1] for p in all_points):.9f})return 0.0;
    return {expression};
}}
vec3 courtyardPavingAlbedo(vec3 position) {{
    vec2 axis=vec2({dx:.9f},{dz:.9f});
    vec2 local=vec2(dot(position.xz,axis),dot(position.xz,vec2(-axis.y,axis.x)));
    vec2 uv=local/{spec['textureMetresPerRepeat']:.4f};
    vec3 grain=textureGrad(Sampler1,uv,dFdx(uv),dFdy(uv)).rgb;
    float luminance=dot(grain,vec3(.299,.587,.114));
    vec2 slabs=local/{spec['pavingUnitMetres']:.4f};
    vec2 edge=min(fract(slabs),1.0-fract(slabs))*{spec['pavingUnitMetres']:.4f};
    float distance=min(edge.x,edge.y),aa=max(fwidth(distance),.001);
    float joint=1.0-smoothstep({spec['jointWidthMetres']*.5:.5f}-aa,{spec['jointWidthMetres']:.5f}+aa,distance);
    float variation=.97+.06*fract(sin(dot(floor(slabs),vec2(127.1,311.7)))*43758.5453);
    return vec3(.55,.54,.51)*clamp(luminance/.5112,.75,1.25)*variation*(1.0-.25*joint);
}}
''')
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    snippet = generate(json.loads((SOURCE / 'low-building-paving.json').read_text()))
    for name in ['campus_ground.fsh', 'campus_reflection.fsh']:
        path = SOURCE / 'shaders' / name
        text = path.read_text()
        if BEGIN in text:
            if args.check:
                assert text.split(BEGIN, 1)[1].split(END, 1)[0] == snippet, name
                continue
            text = text.split(BEGIN, 1)[0] + BEGIN + snippet + END + text.split(END, 1)[1]
        else:
            assert not args.check, 'Missing courtyard paving: ' + name
            at = text.index('// BEGIN GENERATED REACTOR GROUND MAPPING')
            text = text[:at] + BEGIN + snippet + END + '\n' + text[at:]
        path.write_text(text)
    print('Courtyard shared paving ' + ('verified' if args.check else 'generated'))


if __name__ == '__main__':
    main()
