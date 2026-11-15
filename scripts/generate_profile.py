"""Generate a verified native compatibility profile for one registered FM27 build."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct

from profile_header import header

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'native' / 'adapter_registry.json'
DEFAULT_ADAPTER_ID = 'local_27_0_1_2494687'


def load_registry():
    registry = json.loads(REGISTRY.read_text(encoding='utf8'))
    if registry.get('schema_version') != 1 or not isinstance(registry.get('adapters'), list):
        raise ValueError('Unsupported native adapter registry schema')
    ids = [item.get('id') for item in registry['adapters']]
    if not all(isinstance(value, str) and value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError('Native adapter IDs must be unique non-empty strings')
    if registry.get('default_adapter') not in ids:
        raise ValueError('Default native adapter is missing from the registry')
    return registry


def adapter_spec(adapter_id):
    registry = load_registry()
    spec = next((item for item in registry['adapters'] if item['id'] == adapter_id), None)
    if spec is None:
        raise ValueError(f'Unknown native adapter: {adapter_id}')
    if not spec.get('enabled'):
        reason = spec.get('reason') or 'Adapter is not enabled'
        raise ValueError(f'Adapter {adapter_id} is not ready: {reason}')
    for key in ('profile_metadata', 'version_metadata', 'reference_sha256', 'output_directory'):
        if not spec.get(key):
            raise ValueError(f'Adapter {adapter_id} is missing registry field: {key}')
    if len(spec['reference_sha256']) != 64:
        raise ValueError(f'Adapter {adapter_id} has an invalid reference SHA256')
    for key in ('profile_metadata', 'version_metadata', 'output_directory'):
        value = Path(spec[key])
        if value.is_absolute() or '..' in value.parts:
            raise ValueError(f'Adapter {adapter_id} has an unsafe {key} path')
    metadata_path = ROOT / 'native' / spec['profile_metadata']
    version_path = ROOT / 'native' / spec['version_metadata']
    metadata = json.loads(metadata_path.read_text(encoding='utf8'))
    version = json.loads(version_path.read_text(encoding='utf8'))
    if metadata.get('reference_sha256', '').lower() != spec['reference_sha256'].lower():
        raise ValueError(f'Adapter {adapter_id} registry/profile SHA256 mismatch')
    if version.get('reference_dll_sha256', '').lower() != spec['reference_sha256'].lower():
        raise ValueError(f'Adapter {adapter_id} registry/version SHA256 mismatch')
    return registry, spec, metadata, version


def pe_sections(raw):
    if raw[:2] != b'MZ':
        raise ValueError('Not a PE file')
    offset = struct.unpack_from('<I', raw, 0x3c)[0]
    if raw[offset:offset + 4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    machine, count = struct.unpack_from('<HH', raw, offset + 4)
    optional_size = struct.unpack_from('<H', raw, offset + 20)[0]
    if machine != 0x8664 or count > 96:
        raise ValueError('Expected x64 PE image')
    result = []
    start = offset + 24 + optional_size
    for index in range(count):
        virtual_size, rva, raw_size, raw_offset = struct.unpack_from(
            '<IIII', raw, start + index * 40 + 8)
        result.append((rva, raw_size, raw_offset))
    return result


def read_rva(raw, sections, rva, size):
    for start, length, offset in sections:
        if start <= rva and rva + size <= start + length:
            value = raw[offset + rva - start:offset + rva - start + size]
            if len(value) == size:
                return value
    raise ValueError(f'Unmapped or truncated range: {rva:#x}, {size}')


def restore_profile(metadata, raw):
    if hashlib.sha256(raw).hexdigest() != metadata['reference_sha256']:
        raise ValueError('Reference DLL SHA256 mismatch; refusing to bless a different build')
    sections = pe_sections(raw)
    profile = copy.deepcopy(metadata)
    for item in profile['ranges']:
        value = read_rva(raw, sections, item['rva'], item['size'])
        if hashlib.sha256(value).hexdigest() != item.pop('sha256'):
            raise ValueError(f'Range checksum mismatch: {item["rva"]:#x}')
        item.pop('size')
        item['hex'] = value.hex()
    return profile


def generate(dll, adapter_id=DEFAULT_ADAPTER_ID):
    registry, spec, metadata, version = adapter_spec(adapter_id)
    raw = Path(dll).read_bytes()
    profile = restore_profile(metadata, raw)
    build_dir = ROOT / 'build' / 'native' / adapter_id
    engine_root = ROOT / 'private' / 'engine' / 'fm27_native'
    adapter_dir = engine_root / spec['output_directory']
    build_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir.mkdir(parents=True, exist_ok=True)

    (build_dir / 'engine_compat_profile.h').write_text(header(profile), encoding='ascii')
    (adapter_dir / 'engine_compat_profile.json').write_text(
        json.dumps(profile, indent=2) + '\n', encoding='utf8')
    (adapter_dir / 'adapter_version.json').write_text(
        json.dumps(version, indent=2) + '\n', encoding='utf8')
    (engine_root / 'adapter_registry.json').write_text(
        json.dumps(registry, indent=2) + '\n', encoding='utf8')

    # Keep the historical single-adapter metadata paths working for existing
    # diagnostic scripts and older callers. Runtime selection uses the registry.
    if adapter_id == registry['default_adapter']:
        legacy_native = ROOT / 'private' / 'native'
        legacy_native.mkdir(parents=True, exist_ok=True)
        (legacy_native / 'engine_compat_profile.h').write_text(header(profile), encoding='ascii')
        (engine_root / 'engine_compat_profile.json').write_text(
            json.dumps(profile, indent=2) + '\n', encoding='utf8')
        (engine_root / 'adapter_version.json').write_text(
            json.dumps(version, indent=2) + '\n', encoding='utf8')
    print(f'Generated adapter {adapter_id} from its exact local reference DLL.')
    return spec, profile, build_dir, adapter_dir


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dll', required=True, type=Path)
    parser.add_argument('--adapter', default=DEFAULT_ADAPTER_ID)
    args = parser.parse_args()
    generate(args.reference_dll, args.adapter)
