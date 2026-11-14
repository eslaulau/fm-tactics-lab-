import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from runtime_layout import (
    FAIL_CLOSED_PLATFORM_STUBS, PLATFORM_PROBE_DLLS, RUNTIME_DLLS,
    resolve_runtime_dlls,
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

    def test_only_icu_runtime_dependencies_are_resolved(self):
        self.assertEqual(RUNTIME_DLLS, ('icuuc65.dll', 'icuin65.dll', 'icudt65.dll'))
        target = self.touch_dll(
            self.game / 'fm_Data' / 'Plugins' / 'x86_64', RUNTIME_DLLS[0])
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(result['found'][RUNTIME_DLLS[0]], target.resolve())
        self.assertEqual(
            result['search_dirs'][0],
            (self.game / 'fm_Data' / 'Plugins' / 'x86_64').resolve())

    def test_plugins_parent_is_supported_fallback(self):
        target = self.touch_dll(self.game / 'fm_Data' / 'Plugins', RUNTIME_DLLS[1])
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(result['found'][RUNTIME_DLLS[1]], target.resolve())
        self.assertNotIn(RUNTIME_DLLS[1], result['missing'])

    def test_bundled_native_libs_are_supported(self):
        target = self.touch_dll(self.native / 'libs', RUNTIME_DLLS[2])
        result = resolve_runtime_dlls(None, self.native)
        self.assertEqual(result['found'][RUNTIME_DLLS[2]], target.resolve())

    def test_platform_runtime_dlls_are_never_resolved_from_game_install(self):
        stubs, probes = self.touch_platform_modules()
        for name in PLATFORM_PROBE_DLLS:
            self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertFalse(any(name in result['found'] for name in PLATFORM_PROBE_DLLS))
        self.assertEqual(result['platform_probes'], probes)
        self.assertEqual(result['platform_stubs'], stubs)
        self.assertFalse(result['missing_platform_probes'])
        self.assertFalse(result['missing_platform_stubs'])
        self.assertTrue(result['offline_platform_boundary'])

    def test_real_steam_and_eos_are_not_required(self):
        for name in RUNTIME_DLLS:
            self.touch_dll(self.native / 'libs', name)
        self.touch_platform_modules()
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertFalse(result['missing'])
        self.assertFalse(result['missing_platform_probes'])
        self.assertFalse(result['ambiguous'])
        self.assertNotIn('steam_api64.dll', result['missing'])
        self.assertNotIn('EOSSDK-Win64-Shipping.dll', result['missing'])

    def test_missing_icu_dependencies_are_reported(self):
        self.touch_platform_modules()
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(set(result['missing']), set(RUNTIME_DLLS))
        self.assertFalse(result['found'])

    def test_conflicting_duplicate_icu_dlls_fail_closed(self):
        name = RUNTIME_DLLS[0]
        first = self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        second = self.touch_dll(self.game / 'fm_Data' / 'Plugins', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertNotIn(name, result['found'])
        self.assertEqual(
            result['ambiguous'][name], (first.resolve(), second.resolve()))

    def test_fail_closed_party_and_playfab_stubs_are_selected_from_bundle(self):
        expected = {
            name: self.touch_dll(self.native / 'platform-stubs', name)
            for name in FAIL_CLOSED_PLATFORM_STUBS
        }
        for name in FAIL_CLOSED_PLATFORM_STUBS:
            self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(result['platform_stubs'], expected)
        self.assertFalse(result['missing_platform_stubs'])

    def test_missing_fail_closed_platform_modules_are_reported(self):
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(
            set(result['missing_platform_stubs']), set(FAIL_CLOSED_PLATFORM_STUBS))
        self.assertEqual(
            set(result['missing_platform_probes']), set(PLATFORM_PROBE_DLLS))
        self.assertFalse(result['platform_stubs'])
        self.assertFalse(result['platform_probes'])

    def test_legacy_probe_flag_cannot_restore_real_platform_dependencies(self):
        for name in RUNTIME_DLLS:
            self.touch_dll(self.native / 'libs', name)
        stubs, probes = self.touch_platform_modules()
        for name in PLATFORM_PROBE_DLLS:
            self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        result = resolve_runtime_dlls(
            self.game, self.native, platform_probe_mode=False)
        self.assertFalse(result['missing'])
        self.assertEqual(result['platform_probes'], probes)
        self.assertEqual(result['platform_stubs'], stubs)
        self.assertTrue(result['offline_platform_boundary'])


if __name__ == '__main__':
    unittest.main()
