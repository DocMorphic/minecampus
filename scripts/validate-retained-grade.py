#!/usr/bin/env python3
"""Carry grade evidence forward only for an isolated decorative-planting edit.

The prior accepted package supplies its original report and exact geometry.
This avoids restoring an obsolete whole-campus cache after storage cleanup.
Any other manifest change, collision change or mesh change fails closed.
"""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'dist-minecraft/exterior'
SOURCE = ROOT / 'minecraft/exterior'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline-jar', type=Path, required=True)
parser.add_argument('--accepted-report', type=Path, required=True)
args = parser.parse_args()
accepted = json.loads(args.accepted_report.read_text())
assert accepted['playablePreviewReady'] is True
assert sha(args.baseline_jar) == accepted['artifact']['sha256']
current_bytes = (DATA / 'manifest.json').read_bytes()
current = json.loads(current_bytes)
prefix = 'src/minecampus-exterior/'
with zipfile.ZipFile(args.baseline_jar) as jar:
    with zipfile.ZipFile(io.BytesIO(jar.read('realworldmc-service.zip'))) as bundle:
        previous_bytes = bundle.read(prefix + 'manifest.json')
        previous = json.loads(previous_bytes)
        report = json.loads(bundle.read(prefix + 'galileo-east-grade-validation.json'))
        assert report['status'].startswith('PASS:')
        assert report['manifestSha256'] == hashlib.sha256(previous_bytes).hexdigest()
        assert report['validatorSha256'] == sha(ROOT / 'scripts/validate-galileo-east-grade.py')
        assert {k: v for k, v in current.items() if k != 'architecture'} == {
            k: v for k, v in previous.items() if k != 'architecture'}
        assert {k: v for k, v in current['architecture'].items() if k != 'lowBuildingSite'} == {
            k: v for k, v in previous['architecture'].items() if k != 'lowBuildingSite'}
        current_site, previous_site = [m['architecture']['lowBuildingSite'] for m in [current, previous]]
        allowed = {'generatorSha256', 'sourceSha256', 'shrubs'}
        assert {k: v for k, v in current_site.items() if k not in allowed} == {
            k: v for k, v in previous_site.items() if k not in allowed}
        plant_file = current_site['shrubs']['meshFile']
        assert plant_file == previous_site['shrubs']['meshFile'] == 'low-building-courtyard-shrubs.ect'
        tile = next(t for t in current['tiles'] if t['file'] == plant_file)
        assert tile['kind'] == 'vegetation' and tile['collisionParts'] == []
        retained = {}
        for name in bundle.namelist():
            if not name.startswith(prefix) or not name.endswith('.ect') or name == prefix + plant_file:
                continue
            digest = hashlib.sha256(bundle.read(name)).hexdigest()
            local = name[len(prefix):]
            assert sha(DATA / local) == digest, local
            retained[local] = digest
        assert len(retained) >= len(previous['tiles']) - 1
        for name, digest in report['tileSha256'].items():
            assert retained[name] == digest
        original_report_sha = hashlib.sha256(bundle.read(prefix + 'galileo-east-grade-validation.json')).hexdigest()
grade = current['galileoEastGrading']
for file_key, hash_key, folder in [('sourceFile', 'sourceSha256', SOURCE),
                                 ('generatorFile', 'generatorSha256', ROOT),
                                 ('rampGeneratorFile', 'rampGeneratorSha256', ROOT),
                                 ('referenceFile', 'referenceSha256', SOURCE)]:
    assert sha(folder / grade[file_key]) == grade[hash_key]
reference = json.loads((SOURCE / grade['referenceFile']).read_text())
for name, digest in reference['sourceFiles'].items():
    assert sha(ROOT / '.cache' / name) == digest
report['manifestSha256'] = hashlib.sha256(current_bytes).hexdigest()
report['retainedEvidence'] = {
    'method': 'Original grade proof plus exact retained geometry; only decorative courtyard planting differs',
    'baselineArtifactSha256': accepted['artifact']['sha256'],
    'baselineManifestSha256': hashlib.sha256(previous_bytes).hexdigest(),
    'originalGradeReportSha256': original_report_sha,
    'retainedMeshFiles': len(retained),
    'excludedDecorativeMesh': plant_file,
    'checkerFile': 'scripts/validate-retained-grade.py',
    'checkerSha256': sha(Path(__file__)),
}
(DATA / 'galileo-east-grade-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: retained grade and', len(retained), 'unchanged packaged meshes verified against accepted artifact')
