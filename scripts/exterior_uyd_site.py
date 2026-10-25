"""Close surveyed outdoor ground gaps around UYD without retiring vegetation."""
import hashlib,json
from pathlib import Path
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys
from exterior_ground_extension import build as extend_ground


def build(ctx):
    root,cache,out,meta=[ctx[k]for k in ('ROOT','CACHE','OUT','metadata')]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/uyd-site.json';spec=json.loads(source.read_text())
    surveys=nearby_surveys(cache,spec['boundsUTM'])
    feet={bid:unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for k,r in surfaces if k=='GroundSurface'])for bid,surfaces in surveys}
    selected=feet[spec['building']].buffer(spec['groundMarginMetres']).intersection(box(*spec['boundsUTM']))
    region=selected.difference(unary_union(list(feet.values())).buffer(spec['groundBuildingGuardMetres']))
    ground=extend_ground(ctx,region,'uyd-approach-ground',spec['groundRuntimeId'],spec['groundBlendMetres'])
    meta['supplementalSurfaces'][-1]['outdoorReconstructed']=False
    assert spec['groundRuntimeId']+len(ground['groundTiles'])<1_000_061_300
    derived=out/'uyd-site-surfaces.json'
    derived.write_text(json.dumps({'ground':ground,'groundDomainUTM':region.__geo_interface__,'qualification':spec['qualification']},indent=2)+'\n')
    meta['architecture']['uydSite']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_uyd_site.py','generatorSha256':sha(Path(__file__)),'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),'derivedFile':derived.name,'derivedSha256':sha(derived),'groundTiles':ground['groundTiles'],'sourceEvidence':spec['sourceEvidence'],'sourceEvidenceSha256':sha(root/'minecraft/exterior'/spec['sourceEvidence']),'qualification':spec['qualification']}
    assert len({t['runtimeId']for t in meta['tiles']})==len(meta['tiles'])
    print('UYD approaches:',len(ground['groundTiles']),'ground tiles;',ground['areaSquareMetres'],'square metres',flush=True)
