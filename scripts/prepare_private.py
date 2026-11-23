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
V1112_RELEASE_SHA256 = '60c1b60b84cabc6362e3f3ebab1b7a4aa9dc27d57bd445af1c026c5ed22b7355'
TRUSTED_RELEASES = {
    RELEASE_SHA256: PAYLOAD_SHA256,
    'e05f81c8100e626bbff838e04e4c8cb9b962e5158a7c6c3c918cde06f95cec22': 'd184d2a0d0b5866ad35e473996536a88cec86c1355754687d1f394165ecec26d',
    '95dda08390893f13b24d974c6743db05270171a636b9b28ed1e1204757c0ee18': '8ce1c96371d1ab23d7552ae5418a8cdd5ddb4996e7672503dba1f5c5cc4541cf',
    # v1112 is pinned by the public Release asset SHA-256. Its .NET managed
    # resource is checked for ZIP integrity and all required archive members.
    V1112_RELEASE_SHA256: None,
}


def extract_v1112_managed_resource(executable):
    """Read the embedded DesktopPayload resource from the v1112 .NET assembly."""
    try:
        import dnfile
    except ImportError as exc:
        raise ValueError('dnfile is required to read v1112 .NET resources') from exc
    pe = dnfile.dnPE(str(executable))
    if pe.net is None:
        raise ValueError('v1112 EXE has no readable CLR/.NET header')
    for resource in pe.net.resources:
        if resource.name == 'DesktopPayload':
            if not isinstance(resource.data, bytes):
                raise ValueError('DesktopPayload exists but is not a raw ZIP byte resource')
            return resource.data
    names = [str(resource.name) for resource in pe.net.resources]
    raise ValueError('DesktopPayload managed resource not found; resources=' + repr(names))


def extract_legacy_overlay(raw):
    """Read the appended ZIP used by earlier release formats."""
    start, end = raw.find(b'PK\\x03\\x04'), raw.rfind(b'PK\\x05\\x06')
    if start < 0 or end < start or end + 22 > len(raw):
        raise ValueError('Appended ZIP payload not found')
    comment_size = struct.unpack_from('<H', raw, end + 20)[0]
    payload = raw[start:end + 22 + comment_size]
    if not payload.startswith(b'PK\\x03\\x04'):
        raise ValueError('Invalid appended ZIP payload')
    return payload


def prepare_release(executable):
    """Read a checksum-pinned release's embedded data without executing the EXE."""
    executable = Path(executable)
    raw = executable.read_bytes()
    release_sha = hashlib.sha256(raw).hexdigest()
    if release_sha not in TRUSTED_RELEASES:
        raise ValueError('Unrecognized Release EXE SHA256; refusing to extract private inputs')
    expected_payload = TRUSTED_RELEASES[release_sha]
    if release_sha == V1112_RELEASE_SHA256:
        payload = extract_v1112_managed_resource(executable)
    else:
        payload = extract_legacy_overlay(raw)
    if expected_payload is not None and hashlib.sha256(payload).hexdigest() != expected_payload:
        raise ValueError('Embedded payload checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError('Embedded payload CRC failure: ' + corrupt)
        members = [('engine/' + name, ROOT / 'private/engine' / name) for name in ASSETS]
        members.append(('source/tactics_ui/catalog.json', ROOT / 'private/catalog.json'))
        for name, _ in members:
            archive.getinfo(name)
        for name, target in members:
            data = archive.read(name)
            if target.suffix == '.json':
                json.loads(data.decode('utf-8-sig'))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print('Prepared local inputs from checksum-pinned release EXE; executable was not run.')


def prepare(source, catalog):
    source, catalog = Path(source).resolve(), Path(catalog).resolve()
    paths = [(source / name, ROOT / 'private/engine' / name) for name in ASSETS]
    paths.append((catalog, ROOT / 'private/catalog.json'))
    missing = [str(src) for src, _ in paths if not src.is_file()]
    if missing:
        raise ValueError('Missing private inputs:\\n' + '\\n'.join(missing))
    for src, _ in paths:
        if src.suffix == '.json':
            json.loads(src.read_text(encoding='utf-8-sig'))
    for src, dest in paths:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    print('Private inputs staged under private/. Do not publish this directory.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-exe', type=Path, help='Checksum-pinned official EXE downloaded from Releases (v1112 supported)')
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
