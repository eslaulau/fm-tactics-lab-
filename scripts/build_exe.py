"""Build a private Windows executable with every enabled registered native adapter."""
import argparse
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import subprocess
import zipfile

from prepare_private import ASSETS
from run import ROOT, check_inputs, stage_source

NATIVE = ROOT / 'private' / 'engine' / 'fm27_native'
REGISTRY = ROOT / 'native' / 'adapter_registry.json'


def enabled_adapters():
    registry = json.loads(REGISTRY.read_text(encoding='utf8'))
    if registry.get('schema_version') != 1:
        raise ValueError('Unsupported native adapter registry schema')
    adapters = [item for item in registry.get('adapters', []) if item.get('enabled') is True]
    if not adapters:
        raise ValueError('No enabled native adapters are registered')
    return registry, adapters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-home', required=True, type=Path,
                        help='Full CPython 3.12 x64 distribution containing Lib and DLLs')
    parser.add_argument('--icon', type=Path, help='Optional local application ICO file')
    parser.add_argument('--csc', type=Path,
                        default=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'))
    args = parser.parse_args()
    check_inputs()
    registry, adapters = enabled_adapters()
    python = args.python_home.resolve()
    for name in ['python.exe', 'python312.dll', 'python3.dll', 'vcruntime140.dll',
                 'vcruntime140_1.dll', 'LICENSE.txt', 'Lib', 'DLLs']:
        if not (python / name).exists():
            raise SystemExit('Missing Python runtime component: ' + name)
    build, dist = ROOT / 'build', ROOT / 'dist'
    build.mkdir(exist_ok=True)
    dist.mkdir(exist_ok=True)
    source = build / 'source'
    stage_source(source)
    library = build / 'python312.zip'
    with zipfile.ZipFile(library, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in (python / 'Lib').rglob('*.py'):
            relative = path.relative_to(python / 'Lib')
            if relative.parts[0] not in {'site-packages', 'ensurepip', 'idlelib', 'tkinter', 'turtledemo', 'test', 'lib2to3'}:
                archive.write(path, relative.as_posix())
    payload = build / 'payload.zip'
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as archive:
        # Use explicit source types and asset paths, never archive the working directory.
        for original in (ROOT / 'src').rglob('*'):
            if original.is_file() and original.suffix in {'.py', '.js', '.css', '.html'} and '__pycache__' not in original.parts:
                relative = original.relative_to(ROOT / 'src')
                archive.write(source / relative, 'source/' + relative.as_posix())
        archive.write(ROOT / 'private/catalog.json', 'source/tactics_ui/catalog.json')
        # Keep the save reader and its licenses alongside the bundled Python runtime.
        for package, module in [('fmsave', 'fmsave'), ('backports-zstd', 'backports/zstd')]:
            dependency = distribution(package)
            for entry in dependency.files:
                name = entry.as_posix()
                if '__pycache__' in entry.parts:
                    continue
                if name.startswith(module + '/') or entry.parts[0].endswith('.dist-info'):
                    archive.write(dependency.locate_file(entry), 'source/vendor/' + name)
        for name in ['python.exe', 'python312.dll', 'python3.dll', 'vcruntime140.dll',
                     'vcruntime140_1.dll', 'LICENSE.txt']:
            archive.write(python / name, 'python/' + name)
        for path in (python / 'DLLs').iterdir():
            if path.suffix.lower() in {'.pyd', '.dll'}:
                archive.write(path, 'python/DLLs/' + path.name)
        archive.write(library, 'python/python312.zip')

        # Common resources and fail-closed platform boundary.
        common_files = list(ASSETS) + [
            'fm27_native/FM27Simulator.exe',
            'fm27_native/engine_compat_profile.json',
            'fm27_native/adapter_version.json',
            'fm27_native/adapter_registry.json',
            'fm27_native/platform-stubs/PartyWin.dll',
            'fm27_native/platform-stubs/PlayFabMultiplayerWin.dll',
            'fm27_native/platform-probes/steam_api64.dll',
            'fm27_native/platform-probes/EOSSDK-Win64-Shipping.dll',
        ]
        for name in common_files:
            archive.write(ROOT / 'private/engine' / name, 'engine/' + name)

        # Store each enabled executable and its own profile under the registry
        # output path. The host still uses the shared fm27_native directory for
        # common resources through FM27_ENGINE_ROOT.
        for adapter in adapters:
            output = Path(adapter['output_directory'])
            if output.is_absolute() or '..' in output.parts:
                raise ValueError('Unsafe adapter output directory: ' + adapter['id'])
            base = NATIVE / output
            for name in ('FM27Simulator.exe', 'engine_compat_profile.json', 'adapter_version.json'):
                source_path = base / name
                if not source_path.is_file():
                    raise ValueError('Missing built adapter artifact: ' + str(source_path))
                archive.write(source_path, 'engine/fm27_native/' + (output / name).as_posix())

    exe = dist / 'FM27-Tactics-Lab-v1112.exe'
    subprocess.run([
        str(args.csc), '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/utf8output',
        *(['/win32icon:' + str(args.icon.resolve())] if args.icon else []),
        '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
        '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
        '/resource:' + str(payload) + ',DesktopPayload', '/out:' + str(exe), str(ROOT / 'Launcher.cs')
    ], check=True)
    adapters_hashes = {
        adapter['id']: hashlib.sha256(
            (NATIVE / adapter['output_directory'] / 'FM27Simulator.exe').read_bytes()
        ).hexdigest()
        for adapter in adapters
    }
    manifest = {
        'version': 'v1112',
        'file': exe.name,
        'payload_sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
        'native_host_sha256': hashlib.sha256((NATIVE / 'FM27Simulator.exe').read_bytes()).hexdigest(),
        'native_adapters': adapters_hashes,
        'sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'private_assets_included': True,
        'public_source_release': False
    }
    (dist / 'private-build.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
