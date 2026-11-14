"""Verify diagnostic probe exports against every pinned Steam/EOS import."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_platform_stub_exports import PEImage, PEFormatError

EXPECTED = {
    'steam_api64.dll': ('steam_api64.dll', 11),
    'EOSSDK-Win64-Shipping.dll': ('eossdk-win64-shipping.dll', 109),
}


def verify_probe(path, metadata):
    image = PEImage(path)
    filename = image.path.name
    if filename not in EXPECTED:
        raise ValueError(f'Unsupported platform probe filename: {filename}')
    module, count = EXPECTED[filename]
    expected = {
        item['name'] for item in metadata['imports']
        if item['dll'].lower() == module
    }
    actual = image.parse_exports()
    names = set(actual['names'])
    if names != expected:
        raise ValueError(
            f'{filename}: export mismatch; missing={sorted(expected - names)}, '
            f'extra={sorted(names - expected)}')
    if actual['function_count'] != count or actual['name_count'] != count:
        raise ValueError(f'{filename}: export count differs from the pinned manifest')
    if len(set(actual['named_function_rvas'])) != count:
        raise ValueError(f'{filename}: API exports must have distinct identifying traps')
    imported = image.parse_imports()
    if imported != ['kernel32.dll']:
        raise ValueError(f'{filename}: unexpected runtime imports: {imported}')
    return {'file': filename, 'machine': 'x64', 'export_count': count,
            'distinct_api_traps': count, 'imports': imported}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dlls', nargs='+', type=Path)
    parser.add_argument('--manifest', type=Path,
                        default=ROOT / 'native/profile_metadata.json')
    args = parser.parse_args()
    metadata = json.loads(args.manifest.read_text(encoding='utf-8'))
    print(json.dumps([verify_probe(path, metadata) for path in args.dlls], indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, KeyError, ValueError, PEFormatError) as error:
        print(f'platform-probe verification failed: {error}', file=sys.stderr)
        raise SystemExit(1)
