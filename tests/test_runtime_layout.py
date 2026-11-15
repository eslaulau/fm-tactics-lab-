import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from runtime_layout import (
    FAIL_CLOSED_PLATFORM_STUBS, PLATFORM_API_DLLS, PLATFORM_PROBE_DLLS,
    RUNTIME_DLLS, resolve_runtime_dlls,
)


class RuntimeLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        self.native = self.root / 'bundle' / 'fm27_native'

    @staticmethod
    def touch_dll(directory, name):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_bytes(b'fixture:' + name.encode('ascii'))
        return path

    def touch_platform_modules(self):
        stubs = {
            name: self.touch_dll(self.native / 'platform-stubs', name)
            for name in FAIL_CLOSED_PLATFORM_STUBS
        }
        probes = {
            name: self.touch_dll(self.native / 'platform-probes', name)
            for name in PLATFORM_PROBE_DLLS
        }
        return stubs, probes

    def test_only_icu_runtime_dependencies_are_resolved_by_default(self):
        self.assertEqual(RUNTIME_DLLS, ('icuuc65.dll', 'icuin65.dll', 'icudt65.dll'))
        target = self.touch_dll(
            self.game / 'fm_Data' / 'Plugins' / 'x86_64', RUNTIME_DLLS[0])
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(result['found'][RUNTIME_DLLS[0]], target.resolve())
        self.assertEqual(result['search_dirs'][0],
                         (self.game / 'fm_Data' / 'Plugins' / 'x86_64').resolve())

    def test_plugins_parent_is_supported_icu_fallback(self):
        target = self.touch_dll(self.game / 'fm_Data' / 'Plugins', RUNTIME_DLLS[1])
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(result['found'][RUNTIME_DLLS[1]], target.resolve())
        self.assertNotIn(RUNTIME_DLLS[1], result['missing'])

    def test_bundled_native_libs_are_supported_for_icu(self):
        target = self.touch_dll(self.native / 'libs', RUNTIME_DLLS[2])
        result = resolve_runtime_dlls(None, self.native)
        self.assertEqual(result['found'][RUNTIME_DLLS[2]], target.resolve())

    def test_diagnostic_mode_uses_only_bundle_fail_fast_modules(self):
        stubs, probes = self.touch_platform_modules()
        for name in PLATFORM_PROBE_DLLS:
            self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(PLATFORM_API_DLLS, PLATFORM_PROBE_DLLS)
        self.assertEqual(result['platform_probes'], probes)
        self.assertEqual(result['platform_stubs'], stubs)
        self.assertFalse(result['missing_platform_probes'])
        self.assertFalse(result['missing_platform_stubs'])
        self.assertFalse(result['platform_api_modules'])
        self.assertTrue(result['offline_platform_boundary'])
        self.assertEqual(result['platform_api_mode'], 'diagnostic')

    def test_genuine_mode_resolves_original_sdk_from_game_plugins(self):
        stubs, _ = self.touch_platform_modules()
        sdk_dir = self.game / 'fm_Data' / 'Plugins' / 'x86_64'
        actual = {name: self.touch_dll(sdk_dir, name) for name in PLATFORM_API_DLLS}
        result = resolve_runtime_dlls(self.game, self.native, platform_api_mode='genuine')
        self.assertEqual(result['platform_api_modules'],
                         {name: path.resolve() for name, path in actual.items()})
        self.assertEqual(result['platform_stubs'], stubs)
        self.assertFalse(result['platform_probes'])
        self.assertFalse(result['missing_platform_api_modules'])
        self.assertFalse(result['missing_platform_stubs'])
        self.assertFalse(result['offline_platform_boundary'])
        self.assertEqual(result['platform_api_mode'], 'genuine')

    def test_genuine_mode_never_falls_back_to_diagnostic_probes(self):
        self.touch_platform_modules()
        for name in RUNTIME_DLLS:
            self.touch_dll(self.native / 'libs', name)
        result = resolve_runtime_dlls(self.game, self.native, platform_api_mode='genuine')
        self.assertFalse(result['platform_api_modules'])
        self.assertFalse(result['platform_probes'])
        self.assertEqual(set(result['missing_platform_api_modules']), set(PLATFORM_API_DLLS))
        self.assertFalse(result['missing_platform_probes'])

    def test_genuine_mode_reports_missing_game_local_sdk_dlls(self):
        result = resolve_runtime_dlls(self.game, self.native, platform_api_mode='genuine')
        self.assertEqual(set(result['missing_platform_api_modules']), set(PLATFORM_API_DLLS))

    def test_genuine_mode_rejects_ambiguous_game_local_sdk_copies(self):
        self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', PLATFORM_API_DLLS[0])
        self.touch_dll(self.game / 'fm_Data' / 'Plugins', PLATFORM_API_DLLS[0])
        result = resolve_runtime_dlls(self.game, self.native, platform_api_mode='genuine')
        self.assertIn(PLATFORM_API_DLLS[0], result['ambiguous_platform_api_modules'])
        self.assertIn(PLATFORM_API_DLLS[1], result['missing_platform_api_modules'])

    def test_missing_icu_dependencies_are_reported(self):
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(set(result['missing']), set(RUNTIME_DLLS))
        self.assertFalse(result['found'])

    def test_conflicting_duplicate_icu_dlls_fail_closed(self):
        name = RUNTIME_DLLS[0]
        first = self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        second = self.touch_dll(self.game / 'fm_Data' / 'Plugins', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertNotIn(name, result['found'])
        self.assertEqual(result['ambiguous'][name], (first.resolve(), second.resolve()))

    def test_party_and_playfab_stubs_always_come_from_the_bundle(self):
        expected = {
            name: self.touch_dll(self.native / 'platform-stubs', name)
            for name in FAIL_CLOSED_PLATFORM_STUBS
        }
        for name in FAIL_CLOSED_PLATFORM_STUBS:
            self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(result['platform_stubs'], expected)
        self.assertFalse(result['missing_platform_stubs'])

    def test_missing_fail_closed_platform_stubs_are_reported(self):
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(set(result['missing_platform_stubs']), set(FAIL_CLOSED_PLATFORM_STUBS))
        self.assertEqual(set(result['missing_platform_probes']), set(PLATFORM_PROBE_DLLS))
        self.assertFalse(result['platform_stubs'])
        self.assertFalse(result['platform_probes'])

    def test_unknown_platform_api_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'platform_api_mode'):
            resolve_runtime_dlls(self.game, self.native, platform_api_mode='fake')


if __name__ == '__main__':
    unittest.main()
