import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('minecampus_installer', ROOT / 'scripts/minecraft.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class NativePackTests(unittest.TestCase):
    def test_pack_is_importable_and_has_no_game_assets_or_credentials(self):
        # Exercise the real archive writer with the verified downloaded dependencies.
        with tempfile.TemporaryDirectory() as folder, patch.object(installer, 'OUTPUT', Path(folder)):
            installer.build()
            with zipfile.ZipFile(Path(folder) / 'Minecampus-0.2.0-mc1.21.1.mrpack') as pack:
                index = json.loads(pack.read('modrinth.index.json'))
                self.assertEqual(index['dependencies']['minecraft'], '1.21.1')
                for item, locked in zip(index['files'], installer.SPEC['files']):
                    payload = installer.dependency(locked).read_bytes()
                    self.assertEqual(item['hashes']['sha512'], hashlib.sha512(payload).hexdigest())
                    self.assertEqual(item['fileSize'], len(payload))
                self.assertFalse(any('service/config.json' in name or 'saves/' in name for name in pack.namelist()))
                with zipfile.ZipFile(io.BytesIO(pack.read('overrides/mods/minecampus-0.2.0.jar'))) as addon:
                    self.assertFalse(any(name.endswith(('.png', '.ogg', '.class')) for name in addon.namelist()))
                    preset = json.loads(addon.read('data/minecampus/worldgen/world_preset/garching.json'))
                    generator = preset['dimensions']['minecraft:overworld']['generator']
                    self.assertEqual((generator['latitude'], generator['longitude']), (48.265, 11.671))
                    # Reject missing function targets in the shipped tick/welcome/help flow.
                    functions = {Path(name).stem for name in addon.namelist() if name.endswith('.mcfunction')}
                    self.assertTrue({'tick', 'welcome', 'kit', 'help', 'night', 'animals'}.issubset(functions))
                    for name in addon.namelist():
                        if name.endswith('.json'):
                            json.loads(addon.read(name))

    def test_install_preserves_other_profiles_worlds_and_local_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            launcher, instance = root / 'launcher', root / 'game'
            launcher.mkdir()
            instance.mkdir()
            (instance / 'config').mkdir()
            config = {'nodeExecutable': '/my/local/node', 'setupComplete': True, 'customSetting': 123}
            (instance / 'config/realworldmc.json').write_text(json.dumps(config))
            (instance / 'realworldmc-service').mkdir()
            private_path = instance / 'realworldmc-service/config.json'
            private_path.write_text('{"cesiumToken":"SYNTHETIC_TEST_TOKEN"}')
            world = instance / 'saves/existing/region'
            world.mkdir(parents=True)
            (world / 'keep.mca').write_bytes(b'existing world')
            original = {'profiles': {'personal': {'name': 'Do not change', 'gameDir': '/personal'}}, 'settings': {'custom': True}}
            profile_path = launcher / 'launcher_profiles.json'
            profile_path.write_text(json.dumps(original))
            base = b'{"id":"1.21.1"}'

            def metadata(url):
                if 'meta.fabricmc.net' in url:
                    return {'id': installer.PROFILE_ID, 'inheritsFrom': '1.21.1'}
                return {'versions': [{'id': '1.21.1', 'sha1': hashlib.sha1(base).hexdigest(), 'url': 'https://example.invalid/version'}]}

            with patch.object(installer, 'INSTANCE', instance), patch.object(installer, 'OUTPUT', root / 'output'), \
                 patch.object(installer, 'get_json', side_effect=metadata), patch.object(installer, 'fetch', return_value=base), \
                 patch.object(installer, 'build', side_effect=installer.addon):
                installer.install(launcher)
                installer.install(launcher)
            updated = json.loads(profile_path.read_text())
            self.assertEqual(updated['profiles']['personal'], original['profiles']['personal'])
            self.assertEqual(updated['settings'], original['settings'])
            self.assertEqual(updated['profiles']['minecampus-java']['gameDir'], str(instance))
            self.assertEqual(json.loads((launcher / 'launcher_profiles.before-minecampus.json').read_text()), original)
            self.assertEqual(json.loads((instance / 'config/realworldmc.json').read_text()), config)
            self.assertEqual(private_path.read_text(), '{"cesiumToken":"SYNTHETIC_TEST_TOKEN"}')
            self.assertEqual((world / 'keep.mca').read_bytes(), b'existing world')


if __name__ == '__main__':
    unittest.main()
