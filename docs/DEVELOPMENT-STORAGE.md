# Development storage

The playable installation lives in `.minecampus/`. Keep its saves, settings and
map credentials. Successful preview upgrades retain the two most recent verified
mod rollback copies. Unrecognized or modified backup files are left alone.

Development builds and comparison snapshots live in ignored `.cache/` folders.
They are separate from the public Git repository and can be much larger than the
installed game. Preserve baselines needed by current validators. Old renderer
build directories under `.cache/exterior-build/` are regenerable; each owned
directory has a `.minecampus-build` marker matching its directory name. Retain the
current renderer and recent build while removing obsolete owned directories.

On macOS/APFS, identical test assets can share disk blocks while remaining
independently editable files:

```sh
python3 scripts/compact-development-cache.py          # inspect duplicates
python3 scripts/compact-development-cache.py --apply  # compact an idle cache
```

This scans large assets in `.cache/`, excludes saves, configuration, service data,
toolchains and renderer build directories, and verifies checksums before atomic
replacement. It uses APFS clones, not hard links. Each later edit remains local to
its own file. The report distinguishes logical duplicate bytes from the measured
change in free disk space; APFS sharing and system snapshots can affect the latter.
Repeated compaction is safe but rehashes the assets. Unsupported filesystems fail
without replacing the affected file.

For future comparison snapshots on macOS, use `cp -c` to clone large immutable
assets when creating the snapshot instead of making full physical copies. Keep
source hashes and test reports, and remove superseded build products after review.
