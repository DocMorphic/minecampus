#!/usr/bin/env python3
"""Generate a compact source-domain mask and shared asphalt shader sampling."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'minecraft/exterior'
BEGIN = '// BEGIN GENERATED PROMENADE MATERIAL\n'
END = '// END GENERATED PROMENADE MATERIAL'


def generate(spec):
    x0, z0, x1, z1 = spec['maskBoundsMC']
    low, high = spec['heightRangeMC']
    return f'''// Existing rendered ground-atlas asphalt coverage; finish is inferred.
uniform sampler2D PromenadeTexture;
float promenadeCoverage(vec3 position) {{
    if(position.y<{low:.4f}||position.y>{high:.4f})return 0.0;
    vec2 uv=vec2((position.x-({x0:.9f}))/{x1-x0:.9f},({z1:.9f}-position.z)/{z1-z0:.9f});
    if(any(lessThan(uv,vec2(0)))||any(greaterThan(uv,vec2(1))))return 0.0;
    return texture(PromenadeTexture,uv).r;
}}
vec3 promenadeAlbedo(vec3 position) {{
    vec2 uv=position.xz/{spec['asphaltMetresPerRepeat']:.4f};
    return textureGrad(Sampler7,uv,dFdx(uv),dFdy(uv)).rgb*{spec['albedoMultiplier']:.4f};
}}
'''


def build_mask(spec):
    from PIL import Image
    source = SOURCE / spec['coverageSource']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == spec['coverageSourceSha256']
    blue = Image.open(source).convert('RGBA').getchannel('B')
    x0, z0, x1, z1 = spec['maskBoundsMC']
    sx0, sz0, sx1, sz1 = spec['coverageSourceBoundsMC']
    box = ((x0-sx0)/(sx1-sx0)*blue.width,
           (sz1-z1)/(sz1-sz0)*blue.height,
           (x1-sx0)/(sx1-sx0)*blue.width,
           (sz1-z0)/(sz1-sz0)*blue.height)
    pixels = blue.transform(tuple(spec['maskSize']), Image.Transform.EXTENT, box,
                            resample=Image.Resampling.BILINEAR)
    target = SOURCE / spec['maskFile']
    pixels.save(target, optimize=True)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = SOURCE / 'promenade-material.json'
    spec = json.loads(path.read_text())
    if args.check:
        assert hashlib.sha256((SOURCE/spec['maskFile']).read_bytes()).hexdigest() == spec['maskSha256']
    else:
        spec['maskSha256'] = build_mask(spec)
        path.write_text(json.dumps(spec, indent=2)+'\n')
    snippet = generate(spec)
    for name in ['campus_ground.fsh', 'campus_reflection.fsh']:
        path = SOURCE / 'shaders' / name
        text = path.read_text()
        assert BEGIN in text
        if args.check:
            assert text.split(BEGIN,1)[1].split(END,1)[0] == snippet, name
        else:
            path.write_text(text.split(BEGIN,1)[0]+BEGIN+snippet+END+text.split(END,1)[1])
    print('Shared promenade mask ' + ('verified' if args.check else 'generated'))


if __name__ == '__main__':
    main()
