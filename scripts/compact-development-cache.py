#!/usr/bin/env python3
"""Share identical macOS cache file storage without linking their future edits.

Dry run by default. Use --apply on an idle development workspace. Only .cache
is scanned; installations, saves, credentials, tools and source stay untouched.
APFS clones preserve independent files, unlike hard links. No download is needed.
"""
import argparse
from collections import defaultdict
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', 'node_modules', 'saves', 'config', 'realworldmc-service',
        'geodata-venv', 'jdk21', 'exterior-build', '__pycache__'}
SUFFIXES = {'.ect', '.jar', '.png', '.jpg', '.json', '.tif', '.mp4'}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def signature(path):
    st = path.lstat()
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def clone_duplicate(source, destination, expected, source_signature, destination_signature):
    """Atomically replace a verified duplicate with an independent APFS clone."""
    if sys.platform != 'darwin':
        raise RuntimeError('Compaction requires macOS/APFS; no copy fallback is used.')
    if source.is_symlink() or destination.is_symlink():
        raise RuntimeError('Symbolic links are excluded.')
    if signature(source) != source_signature or signature(destination) != destination_signature:
        raise RuntimeError(f'Cache changed during scan: {source} or {destination}; stop build processes and retry.')
    temporary = destination.with_name('.compact-' + uuid.uuid4().hex)
    libc = ctypes.CDLL(None, use_errno=True)
    clonefile = libc.clonefile
    clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    clonefile.restype = ctypes.c_int
    try:
        if clonefile(os.fsencode(source), os.fsencode(temporary), 0):
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(destination))
        shutil.copystat(destination, temporary)
        if digest(temporary) != expected:
            raise RuntimeError('Cloned content failed checksum verification.')
        if signature(source) != source_signature or signature(destination) != destination_signature:
            raise RuntimeError('Cache changed during clone; original retained.')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    cache = ROOT / '.cache'
    if cache.is_symlink():
        raise RuntimeError('Cache directory must not be a symbolic link.')
    groups = defaultdict(list)
    for base, directories, files in os.walk(cache, followlinks=False):
        directories[:] = sorted(d for d in directories
                                if d not in SKIP and not Path(base, d).is_symlink())
        for name in sorted(files):
            path = Path(base, name)
            if path.suffix not in SUFFIXES or path.is_symlink():
                continue
            size = path.stat().st_size
            if size >= 1024 * 1024:
                groups[size].append(path)
    report = {'apply': args.apply, 'freeBefore': shutil.disk_usage(ROOT).free,
              'duplicates': 0, 'duplicateLogicalBytes': 0, 'filesHashed': 0}
    last_update = time.monotonic()
    for size, paths in sorted(groups.items(), reverse=True):
        if len(paths) < 2:
            continue
        canonical = {}
        for path in paths:
            before = signature(path)
            checksum = digest(path)
            if signature(path) != before:
                raise RuntimeError('File changed during scan: ' + str(path))
            report['filesHashed'] += 1
            if checksum in canonical:
                source, source_signature = canonical[checksum]
                # Existing hard links already share storage. Replacing one
                # would change the canonical inode's link count and ctime.
                if before[:2] == source_signature[:2]:
                    continue
                if args.apply:
                    clone_duplicate(source, path, checksum, source_signature, before)
                report['duplicates'] += 1
                report['duplicateLogicalBytes'] += size
            else:
                canonical[checksum] = path, before
            if time.monotonic() - last_update >= 20:
                print(json.dumps(report), flush=True)
                last_update = time.monotonic()
    report['freeAfter'] = shutil.disk_usage(ROOT).free
    report['freeSpaceChangeBytes'] = report['freeAfter'] - report['freeBefore']
    # Logical duplicate bytes are not guaranteed physical savings (APFS may
    # already share blocks). Report measured volume space separately.
    if args.apply:
        (cache / 'compaction-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
