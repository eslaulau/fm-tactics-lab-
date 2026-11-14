"""Verify compiled fail-closed platform stub PE exports against the pinned FM27 import manifest."""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DLLS = {
    'PartyWin.dll': 'partywin.dll',
    'PlayFabMultiplayerWin.dll': 'playfabmultiplayerwin.dll',
}
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_NT_OPTIONAL_HDR64_MAGIC = 0x20B
IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_ORDINAL_FLAG64 = 0x8000000000000000


class PEFormatError(ValueError):
    """Raised when a compiled stub is not a valid x64 PE image."""


class PEImage:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if len(self.data) < 0x40 or self.data[:2] != b'MZ':
            raise PEFormatError(f'{self.path}: missing DOS header')
        self.pe_offset = self._u32(0x3C)
        if self._slice(self.pe_offset, 4) != b'PE\0\0':
            raise PEFormatError(f'{self.path}: missing PE signature')
        machine, section_count = struct.unpack('<HH', self._slice(self.pe_offset + 4, 4))
        optional_size = self._u16(self.pe_offset + 20)
        if machine != IMAGE_FILE_MACHINE_AMD64:
            raise PEFormatError(f'{self.path}: expected x64 machine, got {machine:#x}')
        if not 0 < section_count <= 96:
            raise PEFormatError(f'{self.path}: invalid section count {section_count}')
        self.optional_offset = self.pe_offset + 24
        if self._u16(self.optional_offset) != IMAGE_NT_OPTIONAL_HDR64_MAGIC:
            raise PEFormatError(f'{self.path}: expected PE32+ optional header')
        if optional_size < 112 + 8 * 2:
            raise PEFormatError(f'{self.path}: optional header is too short')
        self.size_of_headers = self._u32(self.optional_offset + 60)
        self.sections = []
        section_offset = self.optional_offset + optional_size
        for index in range(section_count):
            offset = section_offset + index * 40
            raw_name = self._slice(offset, 8).split(b'\0', 1)[0]
            virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack(
                '<IIII', self._slice(offset + 8, 16))
            characteristics = self._u32(offset + 36)
            self.sections.append({
                'name': raw_name.decode('ascii', errors='replace'),
                'virtual_address': virtual_address,
                'virtual_size': virtual_size,
                'raw_size': raw_size,
                'raw_pointer': raw_pointer,
                'characteristics': characteristics,
            })
        self.number_of_rva_and_sizes = self._u32(self.optional_offset + 108)

    def _slice(self, offset, size):
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise PEFormatError(f'{self.path}: file range out of bounds')
        return self.data[offset:offset + size]

    def _u16(self, offset):
        return struct.unpack('<H', self._slice(offset, 2))[0]

    def _u32(self, offset):
        return struct.unpack('<I', self._slice(offset, 4))[0]

    def _u64(self, offset):
        return struct.unpack('<Q', self._slice(offset, 8))[0]

    def rva_to_offset(self, rva, size=1):
        if rva < self.size_of_headers and rva + size <= self.size_of_headers:
            self._slice(rva, size)
            return rva
        for section in self.sections:
            start = section['virtual_address']
            raw_size = section['raw_size']
            delta = rva - start
            if delta >= 0 and delta + size <= raw_size:
                offset = section['raw_pointer'] + delta
                self._slice(offset, size)
                return offset
        raise PEFormatError(f'{self.path}: unmapped RVA {rva:#x} size {size}')

    def read_rva(self, rva, size):
        return self._slice(self.rva_to_offset(rva, size), size)

    def c_string(self, rva, max_length=4096):
        offset = self.rva_to_offset(rva)
        end_limit = min(len(self.data), offset + max_length)
        end = self.data.find(b'\0', offset, end_limit)
        if end < 0:
            raise PEFormatError(f'{self.path}: unterminated string at RVA {rva:#x}')
        return self.data[offset:end].decode('ascii')

    def directories(self):
        if self.number_of_rva_and_sizes < 2:
            raise PEFormatError(f'{self.path}: missing PE data directories')
        export = struct.unpack('<II', self._slice(self.optional_offset + 112, 8))
        imports = struct.unpack('<II', self._slice(self.optional_offset + 120, 8))
        return export, imports

    def parse_exports(self):
        (export_rva, export_size), _ = self.directories()
        if not export_rva or export_size < 40:
            raise PEFormatError(f'{self.path}: missing export directory')
        fields = struct.unpack('<IIHHIIIIIII', self.read_rva(export_rva, 40))
        (_characteristics, _timestamp, _major, _minor, _module_name, _base,
         function_count, name_count, functions_rva, names_rva, ordinals_rva) = fields
        if not function_count or not name_count or function_count > 4096 or name_count > 4096:
            raise PEFormatError(f'{self.path}: invalid export counts')
        function_data = self.read_rva(functions_rva, function_count * 4)
        name_data = self.read_rva(names_rva, name_count * 4)
        ordinal_data = self.read_rva(ordinals_rva, name_count * 2)
        functions = list(struct.unpack('<' + 'I' * function_count, function_data))
        names = []
        named_function_rvas = []
        for index in range(name_count):
            name_rva = struct.unpack_from('<I', name_data, index * 4)[0]
            ordinal = struct.unpack_from('<H', ordinal_data, index * 2)[0]
            if ordinal >= function_count:
                raise PEFormatError(f'{self.path}: export ordinal is out of range')
            names.append(self.c_string(name_rva))
            function_rva = functions[ordinal]
            if export_rva <= function_rva < export_rva + export_size:
                raise PEFormatError(f'{self.path}: forwarded exports are not allowed')
            if not any(
                section['virtual_address'] <= function_rva <
                section['virtual_address'] + max(section['virtual_size'], section['raw_size'])
                and section['characteristics'] & IMAGE_SCN_MEM_EXECUTE
                for section in self.sections
            ):
                raise PEFormatError(f'{self.path}: export target is not in executable code')
            named_function_rvas.append(function_rva)
        return {
            'function_count': function_count,
            'name_count': name_count,
            'names': names,
            'named_function_rvas': named_function_rvas,
        }

    def parse_imports(self):
        _, (import_rva, import_size) = self.directories()
        if not import_rva or import_size < 20:
            raise PEFormatError(f'{self.path}: missing import directory')
        dlls = []
        descriptor_count = min(import_size // 20, 4096)
        terminated = False
        for index in range(descriptor_count):
            fields = struct.unpack('<IIIII', self.read_rva(import_rva + index * 20, 20))
            original_thunk, _timestamp, _forwarder, name_rva, first_thunk = fields
            if not name_rva and not first_thunk:
                terminated = True
                break
            dlls.append(self.c_string(name_rva).lower())
            lookup_rva = original_thunk or first_thunk
            if not lookup_rva or not first_thunk:
                raise PEFormatError(f'{self.path}: invalid import thunk table')
            for thunk_index in range(4096):
                value = self._u64(self.rva_to_offset(lookup_rva + thunk_index * 8, 8))
                if not value:
                    break
                if value & IMAGE_ORDINAL_FLAG64:
                    continue
                self.c_string((value & 0x7FFFFFFFFFFFFFFF) + 2)
            else:
                raise PEFormatError(f'{self.path}: unterminated import thunk table')
        if not terminated:
            raise PEFormatError(f'{self.path}: unterminated import descriptor table')
        return sorted(set(dlls))


def expected_import_names(metadata, module_name):
    return {
        item['name'] for item in metadata['imports']
        if item['dll'].lower() == module_name
    }


def verify_stub(path, metadata):
    image = PEImage(path)
    filename = image.path.name
    if filename not in EXPECTED_DLLS:
        raise ValueError(f'Unsupported platform stub filename: {filename}')
    module_name = EXPECTED_DLLS[filename]
    expected = expected_import_names(metadata, module_name)
    actual = image.parse_exports()
    actual_names = set(actual['names'])
    if not expected:
        raise ValueError(f'No pinned engine imports found for {filename}')
    if actual_names != expected:
        missing = sorted(expected - actual_names)
        extra = sorted(actual_names - expected)
        raise ValueError(f'{filename}: export mismatch; missing={missing}, extra={extra}')
    if actual['function_count'] != len(expected) or actual['name_count'] != len(expected):
        raise ValueError(f'{filename}: export table counts do not match the manifest')
    if len(set(actual['named_function_rvas'])) != 1:
        raise ValueError(f'{filename}: exports do not all point to one fail-fast handler')
    imported_dlls = image.parse_imports()
    if imported_dlls != ['kernel32.dll']:
        raise ValueError(f'{filename}: unexpected runtime imports: {imported_dlls}')
    return {
        'file': filename,
        'machine': 'x64',
        'export_count': len(actual_names),
        'all_exports_share_fail_fast_handler': True,
        'imports': imported_dlls,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dlls', nargs='+', type=Path)
    parser.add_argument('--manifest', type=Path,
                        default=ROOT / 'native' / 'profile_metadata.json')
    args = parser.parse_args()
    metadata = json.loads(args.manifest.read_text(encoding='utf-8'))
    results = [verify_stub(path, metadata) for path in args.dlls]
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, KeyError, ValueError, PEFormatError, struct.error) as error:
        print(f'platform-stub verification failed: {error}', file=sys.stderr)
        raise SystemExit(1)
