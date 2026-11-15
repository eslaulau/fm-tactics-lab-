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
LOCAL_ID = 'local_27_0_1_2494687'
LOCAL_SHA = 'f79b0a3413dd0e3f461b0afbc3ff397003f4a26d7525a30717428de6a8b91196'


class NativeBuildRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.native = Path(self.temp.name) / 'fm27_native'
        self.native.mkdir()
        self.registry = json.loads(REGISTRY.read_text(encoding='utf8'))
        (self.native / 'adapter_registry.json').write_text(
            json.dumps(self.registry), encoding='utf8')

    def test_default_profile_is_local_and_matches_the_reference_binary(self):
        loaded = load_adapter_registry(self.native)
        self.assertEqual(loaded['default_adapter'], LOCAL_ID)
        self.assertEqual(len(loaded['adapters']), 1)
        spec, selection = select_adapter(loaded, LOCAL_SHA)
        self.assertEqual(spec['id'], LOCAL_ID)
        self.assertEqual(spec['distribution'], 'local')
        self.assertEqual(selection, 'exact_sha256')

    def test_explicit_profile_selection_is_supported_for_version_trials(self):
        spec, selection = select_adapter(self.registry, '0' * 64, LOCAL_ID)
        self.assertEqual(spec['id'], LOCAL_ID)
        self.assertEqual(selection, 'explicit')

    def test_unknown_hash_uses_the_single_local_build_candidate(self):
        spec, selection = select_adapter(self.registry, '0' * 64)
        self.assertEqual(spec['id'], LOCAL_ID)
        self.assertEqual(selection, 'single_adapter_compatibility_candidate')

    def test_unknown_hash_is_ambiguous_when_multiple_build_profiles_are_enabled(self):
        second = {
            'id': 'local_test_next_build',
            'distribution': 'local',
            'enabled': True,
            'reference_sha256': '1' * 64,
            'profile_metadata': 'profile_metadata.json',
            'version_metadata': 'adapter_version.json',
            'output_directory': 'adapters/local_test_next_build'
        }
        registry = dict(self.registry)
        registry['adapters'] = [dict(self.registry['adapters'][0]), second]
        with self.assertRaisesRegex(ValueError, '明确选择'):
            select_adapter(registry, '0' * 64)

    def test_exact_hash_wins_when_multiple_build_profiles_are_enabled(self):
        second = {
            'id': 'local_test_next_build',
            'distribution': 'local',
            'enabled': True,
            'reference_sha256': '1' * 64,
            'profile_metadata': 'profile_metadata.json',
            'version_metadata': 'adapter_version.json',
            'output_directory': 'adapters/local_test_next_build'
        }
        registry = dict(self.registry)
        registry['adapters'] = [dict(self.registry['adapters'][0]), second]
        spec, selection = select_adapter(registry, '1' * 64)
        self.assertEqual(spec['id'], 'local_test_next_build')
        self.assertEqual(selection, 'exact_sha256')

    def test_known_disabled_build_does_not_fall_back_to_another_profile(self):
        registry = json.loads(json.dumps(self.registry))
        registry['adapters'].append({
            'id': 'local_disabled_build',
            'distribution': 'local',
            'enabled': False,
            'reference_sha256': '2' * 64,
            'output_directory': 'adapters/local_disabled_build',
            'reason': 'This local binary build has not been validated.'
        })
        with self.assertRaisesRegex(ValueError, '尚未启用'):
            select_adapter(registry, '2' * 64)

    def test_profile_output_path_cannot_escape_the_native_bundle(self):
        spec = dict(self.registry['adapters'][0])
        spec['output_directory'] = '../outside'
        with self.assertRaisesRegex(ValueError, '不安全'):
            _adapter_paths(self.native, spec)

    def test_registered_profile_and_version_metadata_agree(self):
        _, spec, metadata, version = adapter_spec(LOCAL_ID)
        self.assertEqual(spec['reference_sha256'], LOCAL_SHA)
        self.assertEqual(metadata['reference_sha256'], LOCAL_SHA)
        self.assertEqual(metadata['activation_flag_rva'], 0x1718f818)
        self.assertEqual(version['reference_dll_sha256'], LOCAL_SHA)


if __name__ == '__main__':
    unittest.main()
