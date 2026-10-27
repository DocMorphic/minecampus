#!/usr/bin/env python3
"""Run inside the imported pack folder to select an installed Node.js 22+ runtime."""
import json
from pathlib import Path
import shutil
import subprocess


def main():
    path = Path.cwd() / 'config/realworldmc.json'
    if not path.is_file():
        raise SystemExit('Run this from the Minecampus instance folder containing config/realworldmc.json.')
    executable = shutil.which('node')
    if not executable:
        raise SystemExit('Install Node.js 22 or newer, reopen Terminal, then retry.')
    version = subprocess.check_output([executable, '--version'], text=True).strip()
    if int(version.lstrip('v').split('.')[0]) < 22:
        raise SystemExit('Node.js 22 or newer is required.')
    config = json.loads(path.read_text())
    config['nodeExecutable'] = str(Path(executable).resolve())
    backup = path.with_suffix('.before-node.json')
    if not backup.exists():
        shutil.copy2(path, backup)
        backup.chmod(0o600)
    temporary = path.with_suffix('.node-pending.json')
    temporary.write_text(json.dumps(config, indent=2) + '\n')
    temporary.replace(path)
    print(f'Configured {version}. Restart Minecraft. Other settings were preserved.')


if __name__ == '__main__':
    main()
