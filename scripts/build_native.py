"""Build one FM27 native adapter while keeping shared runtime assets in one bundle."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from generate_profile import DEFAULT_ADAPTER_ID, adapter_spec, generate, ROOT

NATIVE = ROOT / 'native'
ENGINE = ROOT / 'private' / 'engine' / 'fm27_native'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dll', required=True, type=Path)
    parser.add_argument('--adapter', default=DEFAULT_ADAPTER_ID,
                        help='Adapter ID from native/adapter_registry.json')
    args = parser.parse_args()
    if not shutil.which('cl'):
        raise SystemExit('Run in an x64 Native Tools Command Prompt for Visual Studio (cl.exe required).')

    registry, spec, _, version = adapter_spec(args.adapter)
    spec, profile, out, adapter_dir = generate(args.reference_dll, args.adapter)
    out.mkdir(parents=True, exist_ok=True)
    for path in NATIVE.iterdir():
        if path.suffix in {'.h', '.cpp', '.manifest'}:
            shutil.copy2(path, out / path.name)
    # generate() writes an adapter-specific compatibility header into this
    # build directory. It is included by fm27_engine_compat.h during compilation.
    subprocess.run([
        'cl', '/nologo', '/O2', '/EHsc', '/std:c++17', 'desktop_host.cpp',
        '/Fe:FM27Simulator.exe', '/Fo:desktop_host.obj', '/link', '/INCREMENTAL:NO',
        '/MANIFEST:EMBED', '/MANIFESTINPUT:host.manifest', 'user32.lib'
    ], cwd=out, check=True)

    # Also build the opt-in in-process bridge. It is loaded only by the
    # BepInEx plugin inside the already-running, normally launched FM process.
    subprocess.run([
        'cl', '/nologo', '/LD', '/O2', '/EHsc', '/std:c++17',
        'inprocess_bridge_exports.cpp', '/Fe:FM27InProcessNative.dll',
        '/Fo:inprocess_bridge_exports.obj', '/link', '/INCREMENTAL:NO',
        'user32.lib', 'bcrypt.lib'
    ], cwd=out, check=True)

    # Test the just-built executable against the exact DLL used to generate
    # this adapter. Do not accept an unverified or merely trial-compatible build
    # as a registered reference adapter.
    check_env = {key: value for key, value in os.environ.items()
                 if key != 'FM27_EXPECTED_DLL_SHA256'}
    check = subprocess.run(
        [str(out / 'FM27Simulator.exe'), '--check-image', str(args.reference_dll.resolve())],
        cwd=out, env=check_env, capture_output=True, text=True, timeout=60)
    if check.stdout:
        print(check.stdout, end='')
    if check.stderr:
        print(check.stderr, file=sys.stderr, end='')
    rows = []
    for line in check.stdout.splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    validation = next((row for row in rows
                       if row.get('event') == 'native_engine_compatibility'), None)
    if check.returncode or not validation or not validation.get('compatible'):
        raise SystemExit('Built adapter did not verify against its exact reference game_plugin.dll')

    adapter_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / 'FM27Simulator.exe', adapter_dir / 'FM27Simulator.exe')
    shutil.copy2(out / 'FM27InProcessNative.dll', adapter_dir / 'FM27InProcessNative.dll')
    version_path = NATIVE / spec['version_metadata']
    shutil.copy2(version_path, adapter_dir / 'adapter_version.json')
    (ENGINE / 'adapter_registry.json').write_text(
        json.dumps(registry, indent=2) + '\n', encoding='utf8')

    # Preserve the original single-host path for existing FMTL call sites.
    # desktop_engine selects an adapter first, then stages its binary here;
    # match scheduling and worker code therefore remain unchanged.
    if args.adapter == registry['default_adapter']:
        shutil.copy2(out / 'FM27Simulator.exe', ENGINE / 'FM27Simulator.exe')
        shutil.copy2(adapter_dir / 'FM27InProcessNative.dll', ENGINE / 'FM27InProcessNative.dll')
        shutil.copy2(adapter_dir / 'engine_compat_profile.json',
                     ENGINE / 'engine_compat_profile.json')
        shutil.copy2(adapter_dir / 'adapter_version.json',
                     ENGINE / 'adapter_version.json')

    stub_dir = ENGINE / 'platform-stubs'
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub_source = out / 'platform_dependency_stub.cpp'
    for filename, define in (
        ('PartyWin.dll', 'BUILD_PARTYWIN_STUB'),
        ('PlayFabMultiplayerWin.dll', 'BUILD_PLAYFAB_STUB'),
    ):
        object_file = out / (Path(filename).stem + '_stub.obj')
        subprocess.run([
            'cl', '/nologo', '/LD', '/O2', '/GS-', '/Zl', f'/D{define}=1',
            str(stub_source), '/Fo' + str(object_file), '/link', '/NODEFAULTLIB',
            '/ENTRY:DllMain', '/SUBSYSTEM:WINDOWS', 'kernel32.lib',
            '/INCREMENTAL:NO', '/OUT:' + str(stub_dir / filename),
        ], cwd=out, check=True)
    verify = subprocess.run([
        sys.executable, str(ROOT / 'scripts/verify_platform_stub_exports.py'),
        str(stub_dir / 'PartyWin.dll'), str(stub_dir / 'PlayFabMultiplayerWin.dll')
    ], cwd=ROOT, capture_output=True, text=True, check=True)
    print(verify.stdout, end='')

    probe_dir = ENGINE / 'platform-probes'
    subprocess.run([
        sys.executable, str(ROOT / 'scripts/build_platform_probe_stubs.py'),
        '--output', str(probe_dir)
    ], cwd=ROOT, check=True)

    print('Built adapter:', args.adapter)
    print('Native host:', adapter_dir / 'FM27Simulator.exe')
    print('In-process bridge:', ENGINE / 'FM27InProcessNative.dll')
    print('Shared offline platform boundary:', ENGINE)


if __name__ == '__main__':
    main()
