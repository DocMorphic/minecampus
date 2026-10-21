#!/usr/bin/env python3
"""Reproduce Mensa validation in the pinned upstream Fabric development harness."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT/'.cache/realworldmc'
REVISION = '6f18d1f3ba5a02dadee4b14bcb96578bf3941d13'


def run(args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path, required=True, help='Java 21 JDK home (not a JRE)')
    parser.add_argument('--capture', action='store_true', help='Also run the hidden native Minecraft client for screenshots')
    args = parser.parse_args()
    if not (args.java_home/'bin/javac').exists():
        raise RuntimeError('--java-home must point to a Java 21 JDK')
    if not UPSTREAM.exists():
        UPSTREAM.mkdir(parents=True)
        run(['git','init',str(UPSTREAM)])
        run(['git','-C',str(UPSTREAM),'remote','add','origin','https://github.com/Teddy563/realworldmc.git'])
        run(['git','-C',str(UPSTREAM),'fetch','--depth','1','origin',REVISION])
        run(['git','-C',str(UPSTREAM),'checkout','--detach','FETCH_HEAD'])
    actual = subprocess.check_output(['git','-C',str(UPSTREAM),'rev-parse','HEAD'],text=True).strip()
    if actual != REVISION:
        raise RuntimeError('The validation checkout has a different revision; use a separate clean checkout at the pinned revision.')
    spec=importlib.util.spec_from_file_location('mensa',ROOT/'scripts/mensa.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    archive=builder.build()
    module=UPSTREAM/'mod'
    fixture=ROOT/'minecraft/mensa/gametest'
    test=module/'src/gametest'
    shutil.copy2(fixture/'MensaTests.java',test/'java/dev/realworldmc/MensaTests.java')
    shutil.copytree(ROOT/'minecraft/mensa/pack/data',test/'resources/data',dirs_exist_ok=True)
    flat=test/'resources/data/minecraft/worldgen/world_preset/flat.json'
    flat.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(fixture/'flat.json',flat)
    meta=test/'resources/fabric.mod.json';data=json.loads(meta.read_text())
    data['entrypoints']['fabric-gametest']=['dev.realworldmc.MensaTests'];meta.write_text(json.dumps(data))
    env={**os.environ,'JAVA_HOME':str(args.java_home.resolve())}
    gradle=['bash',str(module/'gradlew'),'-p',str(module),'--console=plain']
    run(gradle+['runGameTest'],env=env)
    if not args.capture:
        return
    client=module/'src/clientcheck'
    shutil.copy2(fixture/'MensaClientCheck.java',client/'java/dev/realworldmc/client/MensaClientCheck.java')
    meta=client/'resources/fabric.mod.json';data=json.loads(meta.read_text())
    data['entrypoints']['client']=['dev.realworldmc.client.MensaClientCheck'];meta.write_text(json.dumps(data))
    world=module/'run-mensa-check/saves/mensa-check'
    shutil.copytree(module/'build/run/gameTest/world',world,dirs_exist_ok=True)
    (world/'datapacks').mkdir(exist_ok=True);shutil.copy2(archive,world/'datapacks'/archive.name)
    build=module/'build.gradle'
    if "runDir 'run-mensa-check'" not in build.read_text():
        with build.open('a') as output:
            output.write("\nloom.runs { mensaCheck { client(); source sourceSets.clientcheck; runDir 'run-mensa-check'; programArg '--width'; programArg '1280'; programArg '--height'; programArg '720' } }\n")
    result=module/'run-mensa-check/mensa-client-result.txt'
    result.unlink(missing_ok=True)
    run(gradle+['runMensaCheck'],env=env)
    if not result.exists() or not result.read_text().startswith('PASS:'):
        raise RuntimeError('Native client capture failed; inspect the isolated client logs.')
    print(result.read_text())


if __name__=='__main__':
    main()
