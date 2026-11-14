import json
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from desktop_engine import load_adapter_registry, select_adapter, _adapter_paths
from generate_profile import adapter_spec

REGISTRY = ROOT / 'native' / 'adapter_registry.json'
STEAM_ID = 'steam_27_0_1_2494687'
STEAM_SHA = 'f79b0a3413dd0e3f461b0afbc3ff397003f4a26d7525a30717428de6a8b91196'


class NativeAdapterRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.native = Path(self.temp.name) / 'fm27_native'
        self.native.mkdir()
        self.registry = json.loads(REGISTRY.read_text(encoding='utf8'))
        (self.native / 'adapter_registry.json').write_text(
            json.dumps(self.registry), encoding='utf8')

    def test_current_steam_adapter_is_the_default_and_exact_reference(self):
        loaded = load_adapter_registry(self.native)
        self.assertEqual(loaded['default_adapter'], STEAM_ID)
        spec, selection = select_adapter(loaded, STEAM_SHA)
        self.assertEqual(spec['id'], STEAM_ID)
        self.assertEqual(selection, 'exact_sha256')
        self.assertEqual(spec['distribution'], 'steam')

    def test_epic_slot_is_reserved_but_not_buildable_without_reference(self):
        epic = next(item for item in self.registry['adapters'] if item['id'] == 'epic_27_0_1')
        self.assertFalse(epic['enabled'])
        self.assertIsNone(epic['reference_sha256'])
        with self.assertRaisesRegex(ValueError, 'not ready'):
            adapter_spec('epic_27_0_1')
        with self.assertRaisesRegex(ValueError, 'not ready'):
            select_adapter(self.registry, STEAM_SHA, 'epic_27_0_1')

    def test_explicit_adapter_selection_is_supported_for_compatibility_trials(self):
        spec, selection = select_adapter(self.registry, '0' * 64, STEAM_ID)
        self.assertEqual(spec['id'], STEAM_ID)
        self.assertEqual(selection, 'explicit')

    def test_unknown_hash_uses_single_enabled_adapter_candidate(self):
        spec, selection = select_adapter(self.registry, '0' * 64)
        self.assertEqual(spec['id'], STEAM_ID)
        self.assertEqual(selection, 'single_adapter_compatibility_candidate')

    def test_unknown_hash_is_ambiguous_when_multiple_adapters_are_enabled(self):
        second = {
            'id': 'test_second',
            'distribution': 'test',
            'enabled': True,
            'reference_sha256': '1' * 64,
            'profile_metadata': 'profile_metadata.json',
            'version_metadata': 'adapter_version.json',
            'output_directory': 'adapters/test_second'
        }
        registry = dict(self.registry)
        registry['adapters'] = [dict(self.registry['adapters'][0]), second]
        with self.assertRaisesRegex(ValueError, '明确选择'):
            select_adapter(registry, '0' * 64)

    def test_exact_hash_wins_even_when_another_adapter_is_enabled(self):
        second = {
            'id': 'test_second',
            'distribution': 'test',
            'enabled': True,
            'reference_sha256': '1' * 64,
            'profile_metadata': 'profile_metadata.json',
            'version_metadata': 'adapter_version.json',
            'output_directory': 'adapters/test_second'
        }
        registry = dict(self.registry)
        registry['adapters'] = [dict(self.registry['adapters'][0]), second]
        spec, selection = select_adapter(registry, '1' * 64)
        self.assertEqual(spec['id'], 'test_second')
        self.assertEqual(selection, 'exact_sha256')

    def test_adapter_output_path_cannot_escape_the_native_bundle(self):
        spec = dict(self.registry['adapters'][0])
        spec['output_directory'] = '../outside'
        with self.assertRaisesRegex(ValueError, '不安全'):
            _adapter_paths(self.native, spec)

    def test_registered_profile_and_version_metadata_agree(self):
        _, spec, metadata, version = adapter_spec(STEAM_ID)
        self.assertEqual(spec['reference_sha256'], STEAM_SHA)
        self.assertEqual(metadata['reference_sha256'], STEAM_SHA)
        self.assertEqual(version['reference_dll_sha256'], STEAM_SHA)


if __name__ == '__main__':
    unittest.main()
