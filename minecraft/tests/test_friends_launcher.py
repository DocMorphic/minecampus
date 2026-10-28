"""Exercise setup preservation and launch routing without signing into Minecraft."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'minecraft/friends'
NODE = shutil.which('node')


@unittest.skipUnless(NODE, 'Node is required to test the bundled setup helper')
class FriendsLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='friends paths with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name)
        self.config = self.bundle / 'data/instances/minecampus/.minecraft/config/realworldmc.json'
        self.config.parent.mkdir(parents=True)
        self.config.write_text(json.dumps({'nodeExecutable': 'node', 'setupComplete': True,
                                          'latitude': 48.265, 'custom': {'keep': 'unchanged'}}))
        shutil.copyfile(SOURCE / 'configure-runtime.cjs', self.bundle / 'configure-runtime.cjs')

    def configure(self):
        return subprocess.run([NODE, str(self.bundle / 'configure-runtime.cjs'), str(self.bundle)],
                              capture_output=True, text=True)

    def test_settings_preserved_and_second_run_does_not_write(self):
        before = json.loads(self.config.read_text())
        result = self.configure()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads(self.config.read_text())
        self.assertEqual(after.pop('nodeExecutable'), str(Path(NODE).resolve()))
        before.pop('nodeExecutable')
        self.assertEqual(after, before)
        timestamp = self.config.stat().st_mtime_ns
        self.assertEqual(self.configure().returncode, 0)
        self.assertEqual(self.config.stat().st_mtime_ns, timestamp)

    def test_invalid_settings_never_overwritten(self):
        for invalid in ['{broken', 'null', '[]']:
            with self.subTest(invalid=invalid):
                self.config.write_text(invalid)
                self.assertNotEqual(self.configure().returncode, 0)
                self.assertEqual(self.config.read_text(), invalid)

    def test_existing_pending_file_not_deleted(self):
        code = '''const fs = require('fs');
const {configure} = require(process.argv[1]);
const pending = process.argv[3] + '.' + process.pid + '.pending';
fs.writeFileSync(pending, 'keep');
try { configure(process.argv[2]); process.exit(2); }
catch(e) { if(e.code !== 'EEXIST' || fs.readFileSync(pending, 'utf8') !== 'keep') process.exit(3); }
'''
        before = self.config.read_bytes()
        result = subprocess.run([NODE, '-e', code, str(self.bundle / 'configure-runtime.cjs'),
                                 str(self.bundle), str(self.config)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), before)

    def launch(self, system, architecture, runtime, script, provide_runtime=True):
        shim = self.bundle / 'test-bin'
        shim.mkdir(exist_ok=True)
        uname = shim / 'uname'
        uname.write_text(f'#!/bin/sh\nif [ "$1" = -s ]; then echo {system}; else echo {architecture}; fi\n')
        uname.chmod(0o755)
        if provide_runtime:
            node = self.bundle / 'runtime' / runtime / 'bin/node'
            node.parent.mkdir(parents=True, exist_ok=True)
            node.write_text('#!/bin/sh\nexec ' + shlex.quote(NODE) + ' "$@"\n')
            node.chmod(0o755)
        launcher = self.bundle / ('launcher/Prism Launcher.app/Contents/MacOS/prismlauncher'
                                  if system == 'Darwin' else 'launcher/PrismLauncher.AppImage')
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text('#!/bin/sh\nprintf "%s\\n" "${APPIMAGE_EXTRACT_AND_RUN:-}" "$@" > "$CAPTURE"\n')
        launcher.chmod(0o755)
        capture = self.bundle / 'launch-args.txt'
        capture.unlink(missing_ok=True)
        target = self.bundle / script
        shutil.copyfile(SOURCE / script, target)
        result = subprocess.run(['bash', str(target)], input='\n', capture_output=True, text=True,
                                env={**os.environ, 'PATH': str(shim) + ':' + os.environ['PATH'], 'CAPTURE': str(capture)})
        return result, capture

    def test_supported_os_and_cpu_routes_with_spaces(self):
        for system, arch, runtime, script in [
            ('Darwin', 'arm64', 'darwin-arm64', 'Play Minecampus.command'),
            ('Darwin', 'x86_64', 'darwin-x64', 'Play Minecampus.command'),
            ('Linux', 'x86_64', 'linux-x64', 'Play Minecampus.sh'),
            ('Linux', 'aarch64', 'linux-arm64', 'Play Minecampus.sh'),
        ]:
            with self.subTest(system=system, arch=arch):
                result, capture = self.launch(system, arch, runtime, script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(capture.read_text().splitlines(),
                                 ['1' if system == 'Linux' else '', '--dir', str(self.bundle / 'data'), '--launch', 'minecampus'])

    def test_wrong_linux_download_stops_before_launch(self):
        result, capture = self.launch('Linux', 'aarch64', 'linux-arm64', 'Play Minecampus.sh', False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('different CPU', result.stdout)
        self.assertFalse(capture.exists())


if __name__ == '__main__':
    unittest.main()
