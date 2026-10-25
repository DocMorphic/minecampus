"""Preview updates must preserve progress and refuse unowned/open installations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('preview', Path(__file__).with_name('install-exterior-preview.py'))
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class PreviewUpdate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.instance = self.root / 'preview'
        for name in ['mods', 'saves/world', 'config', 'realworldmc-service']:
            (self.instance / name).mkdir(parents=True)
        self.old = self.instance / 'mods/realworldmc.jar'
        self.new = self.root / 'new.jar'
        for path, version in [(self.old, 'old'), (self.new, 'new')]:
            with zipfile.ZipFile(path, 'w') as jar:
                jar.writestr('fabric.mod.json', json.dumps({'id': 'realworldmc', 'version': version}))
        (self.instance / 'saves/world/level.dat').write_bytes(b'player inventory and edits')
        (self.instance / 'saves/world/session.lock').write_bytes(b'lock')
        (self.instance / 'realworldmc-service/config.json').write_text('{"private":"fixture"}')
        self.record = {'previewInstance': str(self.instance), 'artifactSha256': preview.digest(self.old)}
        (self.instance / 'preview-installation.json').write_text(json.dumps(self.record))
        self.before = preview.snapshot(self.instance / 'saves')
        self.old_bytes = self.old.read_bytes()
        verified = patch.object(preview, 'verify_artifact', return_value={'sha256': preview.digest(self.new)})
        verified.start()
        self.addCleanup(verified.stop)

    def test_update_preserves_progress_settings_and_backup(self):
        preview.update(self.instance, self.new)
        self.assertEqual(preview.snapshot(self.instance / 'saves'), self.before)
        self.assertEqual(self.old.read_bytes(), self.new.read_bytes())
        self.assertEqual((self.instance / 'realworldmc-service/config.json').read_text(), '{"private":"fixture"}')
        backup = self.instance / 'artifact-backups' / self.record['artifactSha256']
        self.assertEqual((backup / self.old.name).read_bytes(), self.old_bytes)
        preview.update(self.instance, self.new)  # Idempotent; no second backup/overwrite.

    def test_modified_mod_is_refused(self):
        with zipfile.ZipFile(self.old, 'a') as jar:
            jar.writestr('user-modification', b'keep me')
        before = self.old.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'differs from its installation record'):
            preview.update(self.instance, self.new)
        self.assertEqual(self.old.read_bytes(), before)
        self.assertEqual(preview.snapshot(self.instance / 'saves'), self.before)

    def test_open_world_is_refused(self):
        lock = self.instance / 'saves/world/session.lock'
        child = subprocess.Popen([sys.executable, '-c', 'import fcntl,sys; f=open(sys.argv[1],"r+"); fcntl.lockf(f,fcntl.LOCK_EX); print("ready",flush=True); sys.stdin.readline()', str(lock)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'ready')
            with self.assertRaisesRegex(RuntimeError, 'open world'):
                preview.update(self.instance, self.new)
            self.assertEqual(self.old.read_bytes(), self.old_bytes)
        finally:
            child.communicate('\n', timeout=10)


class PreviewArtifactReview(unittest.TestCase):
    def test_release_and_reviewed_upgrade_remain_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reports = root / 'minecraft/exterior'
            reports.mkdir(parents=True)
            released, upgrade = root / 'released.jar', root / 'upgrade.jar'
            released.write_bytes(b'released artifact')
            upgrade.write_bytes(b'reviewed development artifact')
            def artifact(path):
                return {'size': path.stat().st_size, 'sha256': preview.digest(path)}
            (reports / 'rcm-technikum-development-validation.json').write_text(json.dumps({'artifact': artifact(released)}))
            review = reports / 'preview-upgrade-development-validation.json'
            review.write_text(json.dumps({'artifact': artifact(upgrade), 'playablePreviewReady': False}))
            with patch.object(preview, 'ROOT', root):
                self.assertEqual(preview.verify_artifact(released), artifact(released))
                with self.assertRaisesRegex(RuntimeError, 'does not match'):
                    preview.verify_artifact(upgrade)
                with self.assertRaisesRegex(RuntimeError, 'has not passed'):
                    preview.verify_artifact(upgrade, True)
                review.write_text(json.dumps({'artifact': artifact(upgrade), 'playablePreviewReady': True}))
                self.assertEqual(preview.verify_artifact(upgrade, True), artifact(upgrade))
                with self.assertRaisesRegex(RuntimeError, 'does not match'):
                    preview.verify_artifact(released, True)
                upgrade.write_bytes(b'tampered development artifact')
                with self.assertRaisesRegex(RuntimeError, 'does not match'):
                    preview.verify_artifact(upgrade, True)


if __name__ == '__main__':
    unittest.main()
