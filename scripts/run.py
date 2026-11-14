"""Run the source edition in a browser; Ctrl+C stops the loopback service."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from prepare_private import ASSETS

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'private' / 'engine' / 'fm27_native'
REGISTRY = ROOT / 'native' / 'adapter_registry.json'


def stage_source(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'src').rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.js', '.css', '.html'} and '__pycache__' not in path.parts:
            target = destination / path.relative_to(ROOT / 'src')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    shutil.copy2(ROOT / 'private/catalog.json', destination / 'tactics_ui/catalog.json')


def check_inputs(adapter='auto'):
    if not REGISTRY.is_file():
        raise ValueError('Missing native/adapter_registry.json. Update the source tree before building.')
    registry = json.loads(REGISTRY.read_text(encoding='utf8'))
    if registry.get('schema_version') != 1:
        raise ValueError('Unsupported native adapter registry schema')
    configured = [item for item in registry.get('adapters', []) if item.get('enabled') is True]
    if adapter == 'auto':
        selected = configured
    else:
        selected = [item for item in registry.get('adapters', []) if item.get('id') == adapter]
        if not selected:
            raise ValueError('Unknown adapter ID: ' + adapter)
        if selected[0].get('enabled') is not True:
            raise ValueError(selected[0].get('reason') or
                             'Adapter is not ready: ' + adapter)
    if not selected:
        raise ValueError('No enabled native adapters are registered.')

    needed = [ROOT / 'private/engine' / name for name in ASSETS]
    needed += [
        ROOT / 'private/catalog.json',
        NATIVE / 'FM27Simulator.exe',
        NATIVE / 'engine_compat_profile.json',
        NATIVE / 'adapter_registry.json',
        NATIVE / 'platform-stubs/PartyWin.dll',
        NATIVE / 'platform-stubs/PlayFabMultiplayerWin.dll',
        NATIVE / 'platform-probes/steam_api64.dll',
        NATIVE / 'platform-probes/EOSSDK-Win64-Shipping.dll'
    ]
    for item in selected:
        relative = Path(item['output_directory'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe native adapter output directory: ' + item['id'])
        adapter_root = NATIVE / relative
        needed.extend((
            adapter_root / 'FM27Simulator.exe',
            adapter_root / 'engine_compat_profile.json',
            adapter_root / 'adapter_version.json'
        ))
    missing = [str(path.relative_to(ROOT)) for path in needed if not path.is_file()]
    if missing:
        raise ValueError('Prepare private assets and build native first. Missing:\n' + '\n'.join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', required=True, type=Path)
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--desktop-mode', choices=('shared', 'private'), default='shared',
                        help='Windows desktop for the headless native host (default: shared).')
    parser.add_argument('--adapter', default='auto',
                        help='Native adapter ID from native/adapter_registry.json, or auto by DLL SHA256.')
    args = parser.parse_args()
    if os.name != 'nt' or sys.version_info[:2] != (3, 12):
        raise SystemExit('This source edition requires Windows x64 and Python 3.12.')
    check_inputs(args.adapter)
    source = ROOT / 'build/source'
    stage_source(source)
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith('FM27_')}
    env.update(FM27_ENGINE_ROOT=str(ROOT / 'private/engine'),
               FM27_GAME_ROOT=str(args.game_root.resolve()),
               FM27_DESKTOP_DATA=str(data),
               FM27_NATIVE_DESKTOP_MODE=args.desktop_mode,
               PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    if args.adapter != 'auto':
        env['FM27_ENGINE_ADAPTER'] = args.adapter
    print(f'Open http://127.0.0.1:{args.port} after the service reports ready.', flush=True)
    try:
        subprocess.run([sys.executable, str(source / 'desktop_server.py'), '--port', str(args.port)],
                       env=env, check=True)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
