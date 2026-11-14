"""Compile the checked-in adapter using an x64 MSVC developer shell."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import os

from generate_profile import generate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dll', required=True, type=Path)
    args = parser.parse_args()
    if not shutil.which('cl'):
        raise SystemExit('Run in an x64 Native Tools Command Prompt for Visual Studio (cl.exe required).')
    generate(args.reference_dll)
    out = ROOT / 'build/native'
    out.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'native').iterdir():
        if path.suffix in {'.h', '.cpp', '.manifest'}:
            shutil.copy2(path, out / path.name)
    shutil.copy2(ROOT / 'private/native/engine_compat_profile.h', out / 'engine_compat_profile.h')
    subprocess.run(['cl', '/nologo', '/O2', '/EHsc', '/std:c++17', 'desktop_host.cpp',
                    '/Fe:FM27Simulator.exe', '/Fo:desktop_host.obj', '/link', '/INCREMENTAL:NO',
                    '/MANIFEST:EMBED', '/MANIFESTINPUT:host.manifest', 'user32.lib'], cwd=out, check=True)

    # Exercise the generated compatibility contract against the exact local DLL.
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
    if check.returncode or not validation or validation.get('disposition') == 'blocked':
        raise SystemExit('Built host rejected the supplied reference game_plugin.dll')

    dest = ROOT / 'private/engine/fm27_native'
    dest.mkdir(parents=True, exist_ok=True)
    stub_dir = dest / 'platform-stubs'
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
    shutil.copy2(out / 'FM27Simulator.exe', dest / 'FM27Simulator.exe')
    shutil.copy2(ROOT / 'native/adapter_version.json', dest / 'adapter_version.json')
    verify = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/verify_platform_stub_exports.py'),
         str(stub_dir / 'PartyWin.dll'), str(stub_dir / 'PlayFabMultiplayerWin.dll')],
        cwd=ROOT, capture_output=True, text=True, check=True)
    print(verify.stdout, end='')
    print('Built FM27Simulator.exe and verified fail-closed platform import stubs')


if __name__ == '__main__':
    main()
