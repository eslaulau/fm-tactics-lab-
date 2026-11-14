"""Prepare ignored runtime inputs from an existing, user-owned tool workspace."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    'fm27_native/editor_manual_default.json',
    'fm27_native/editor_advanced_snapshot.json',
    'fm27_native/editor_setpieces_default.json',
    'fm27_native/fixtures/match.pkm',
    'fm27_research/setpiece_enum_catalog.json',
)
RELEASE_SHA256 = 'b18594de3fcfecbb520e73c86555e122eb899dbadc2ff3402dd0f839329f1614'
PAYLOAD_SHA256 = '8ec66ee7528d0ad60161207b93fedee2ec5cf97dc73af9314d719c289070fc6d'
TRUSTED_RELEASES = {
    RELEASE_SHA256: PAYLOAD_SHA256,
    'e05f81c8100e626bbff838e04e4c8cb9b962e5158a7c6c3c918cde06f95cec22': 'd184d2a0d0b5866ad35e473996536a88cec86c1355754687d1f394165ecec26d',
    '95dda08390893f13b24d974c6743db05270171a636b9b28ed1e1204757c0ee18': '8ce1c96371d1ab23d7552ae5418a8cdd5ddb4996e7672503dba1f5c5cc4541cf',
    # Official v1112 Release asset digest published by GitHub. The pinned EXE
    # hash authenticates the complete embedded payload, so no second ZIP hash
    # is needed for this release.
    '60c1b60b84cabc6362e3f3ebab1b7a4aa9dc27d57bd445af1c026c5ed22b7355': None,
}


def prepare_release(executable):
    """Read embedded data from a SHA256-pinned release EXE without executing it."""
    raw = Path(executable).read_bytes()
    release_hash = hashlib.sha256(raw).hexdigest()
    if release_hash not in TRUSTED_RELEASES:
        raise ValueError('Unrecognized release EXE: SHA256 does not match a verified release')
    expected_payload = TRUSTED_RELEASES[release_hash]
    start, end = raw.find(b'PK\x03\x04'), raw.rfind(b'PK\x05\x06')
    if start < 0 or end < start or end + 22 > len(raw):
        raise ValueError('Embedded payload not found')
    comment_size = struct.unpack_from('<H', raw, end + 20)[0]
    payload = raw[start:end + 22 + comment_size]
    if expected_payload is not None and hashlib.sha256(payload).hexdigest() != expected_payload:
        raise ValueError('Embedded payload checksum mismatch')

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [('engine/' + name, ROOT / 'private/engine' / name) for name in ASSETS]
        members.append(('source/tactics_ui/catalog.json', ROOT / 'private/catalog.json'))

        # Read and validate all required entries before writing anything.
        extracted = []
        for name, target in members:
            data = archive.read(name)  # Also verifies the member CRC.
            if target.suffix == '.json':
                json.loads(data.decode('utf-8-sig'))
            extracted.append((data, target))

    for data, target in extracted:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print('Prepared local inputs from verified release EXE; executable was not run.')


def prepare(source, catalog):
    source, catalog = Path(source).resolve(), Path(catalog).resolve()
    paths = [(source / name, ROOT / 'private/engine' / name) for name in ASSETS]
    paths.append((catalog, ROOT / 'private/catalog.json'))
    missing = [str(src) for src, _ in paths if not src.is_file()]
    if missing:
        raise ValueError('Missing private inputs:\n' + '\n'.join(missing))
    for src, _ in paths:
        if src.suffix == '.json':
            json.loads(src.read_text(encoding='utf-8-sig'))
    for src, dest in paths:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    print('Private inputs staged under private/. Do not publish this directory.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-exe', type=Path,
                        help='Official EXE downloaded from a verified GitHub Release (v1112 is supported)')
    parser.add_argument('--assets-root', type=Path,
                        help='Existing engine workspace, not the game installation')
    parser.add_argument('--catalog', type=Path,
                        help='Matching tactics_ui/catalog.json from that tool version')
    args = parser.parse_args()
    if args.release_exe:
        if args.assets_root or args.catalog:
            parser.error('Use --release-exe alone, or --assets-root together with --catalog')
        prepare_release(args.release_exe)
    elif args.assets_root and args.catalog:
        prepare(args.assets_root, args.catalog)
    else:
        parser.error('Provide --release-exe, or both --assets-root and --catalog')


if __name__ == '__main__':
    main()
