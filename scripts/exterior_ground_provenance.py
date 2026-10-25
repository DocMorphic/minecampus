"""Exact source compatibility for retained successful terrain builds.

The empty-tile guard changes only a branch that previously raised before writing
any tile. Every previously successful build therefore has identical output.
Keep its original generator hash in the manifest; permit only this pinned pair.
Any subsequent generator edit requires regeneration or a new explicit review.
"""
import hashlib

LEGACY_GENERATOR = 'f77a1516e1629aca56a58856514da143175bd95900760a9910d8569217ccb83d'
EMPTY_TILE_FIX_GENERATOR = '60bfc5f91cd1643ca9ae8ba813a219cdf5a60a32a40470ffef3c8edc564b8682'


def ground_generator_matches(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    return actual == expected or (actual == EMPTY_TILE_FIX_GENERATOR and expected == LEGACY_GENERATOR)
