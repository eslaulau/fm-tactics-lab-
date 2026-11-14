"""Compile the checked-in adapter using an x64 MSVC developer shell."""
import argparse
from pathlib import Path
import shutil
import subprocess

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
    print('Built FM27Simulator.exe and fail-closed PartyWin/PlayFab import stubs')


if __name__ == '__main__':
    main()
