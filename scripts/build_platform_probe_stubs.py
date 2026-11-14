"""Build API-identifying, fail-fast Steam/EOS diagnostic DLLs from the pinned import manifest."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    'steam_api64.dll': ('steam_api64.dll', 11),
    'EOSSDK-Win64-Shipping.dll': ('eossdk-win64-shipping.dll', 109),
}
IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def imports_for(metadata, module):
    names = sorted({
        row['name'] for row in metadata['imports']
        if row['dll'].lower() == module
    })
    if not names:
        raise ValueError(f'No imports found for {module}')
    invalid = [name for name in names if not IDENTIFIER.fullmatch(name)]
    if invalid:
        raise ValueError(f'{module} contains unsupported non-name imports: {invalid}')
    return names


def build(output):
    if not shutil.which('cl'):
        raise SystemExit('Run in an x64 Native Tools Command Prompt for Visual Studio (cl.exe required).')
    metadata = json.loads((ROOT / 'native/profile_metadata.json').read_text(encoding='utf-8'))
    template = (ROOT / 'native/platform_probe_stub_template.cpp').read_text(encoding='utf-8')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for filename, (module, expected_count) in MODULES.items():
        names = imports_for(metadata, module)
        if len(names) != expected_count:
            raise ValueError(f'{filename}: manifest has {len(names)} names, expected {expected_count}')
        source = template.replace('@MODULE_NAME@', filename).replace(
            '@WRAPPERS@', '\n'.join(f'DEFINE_PLATFORM_PROBE({name})' for name in names))
        stem = Path(filename).stem
        source_path = output / f'{stem}_probe.generated.cpp'
        def_path = output / f'{stem}_probe.generated.def'
        object_path = output / f'{stem}_probe.obj'
        dll_path = output / filename
        source_path.write_text(source, encoding='utf-8', newline='\n')
        exports = ['LIBRARY "' + filename + '"', 'EXPORTS']
        exports.extend(f'    {name}=Probe_{name}' for name in names)
        def_path.write_text('\n'.join(exports) + '\n', encoding='ascii', newline='\n')
        subprocess.run([
            'cl', '/nologo', '/LD', '/O2', '/GS-', '/Zl', str(source_path),
            '/Fo' + str(object_path), '/link', '/NODEFAULTLIB', '/ENTRY:DllMain',
            '/SUBSYSTEM:WINDOWS', 'kernel32.lib', '/INCREMENTAL:NO',
            '/DEF:' + str(def_path), '/OUT:' + str(dll_path),
        ], cwd=output, check=True)
        results.append({'file': filename, 'expected_exports': expected_count,
                        'built': str(dll_path)})
    verify = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/verify_platform_probe_stubs.py')] +
        [str(output / filename) for filename in MODULES],
        cwd=ROOT, capture_output=True, text=True, check=True)
    print(verify.stdout, end='')
    print('Built API-identifying fail-fast Steam/EOS diagnostic probes.')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='Directory for diagnostic probe DLLs; do not use as production platform runtimes')
    args = parser.parse_args()
    build(args.output)


if __name__ == '__main__':
    main()
