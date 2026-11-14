import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from runtime_layout import (
    FAIL_CLOSED_PLATFORM_STUBS, RUNTIME_DLLS, resolve_runtime_dlls,
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

    def test_x64_plugins_directory_is_first_priority(self):
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

    def test_bundled_libs_are_fallback_when_game_root_is_selected(self):
        target = self.touch_dll(self.native / 'libs', RUNTIME_DLLS[4])
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(result['found'][RUNTIME_DLLS[4]], target.resolve())

    def test_all_real_dependencies_can_be_split_across_known_directories(self):
        directories = (
            self.game / 'fm_Data' / 'Plugins' / 'x86_64',
            self.game / 'fm_Data' / 'Plugins',
            self.game / 'fm_Data',
            self.game,
            self.native / 'libs',
        )
        for name, directory in zip(RUNTIME_DLLS, directories):
            self.touch_dll(directory, name)
        for name in FAIL_CLOSED_PLATFORM_STUBS:
            self.touch_dll(self.native / 'platform-stubs', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(set(result['found']), set(RUNTIME_DLLS))
        self.assertFalse(result['missing'])
        self.assertFalse(result['ambiguous'])
        self.assertEqual(set(result['platform_stubs']), set(FAIL_CLOSED_PLATFORM_STUBS))
        self.assertFalse(result['missing_platform_stubs'])

    def test_missing_real_dependencies_are_reported(self):
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(set(result['missing']), set(RUNTIME_DLLS))
        self.assertFalse(result['found'])

    def test_conflicting_duplicate_dlls_fail_closed(self):
        name = RUNTIME_DLLS[3]
        first = self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        second = self.touch_dll(self.game / 'fm_Data' / 'Plugins', name)
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertNotIn(name, result['found'])
        self.assertEqual(
            result['ambiguous'][name], (first.resolve(), second.resolve()))

    def test_fail_closed_stubs_are_selected_from_bundle_only(self):
        stub_dir = self.native / 'platform-stubs'
        expected = {}
        for name in FAIL_CLOSED_PLATFORM_STUBS:
            expected[name] = self.touch_dll(stub_dir, name)
            self.touch_dll(self.game / 'fm_Data' / 'Plugins' / 'x86_64', name)
        result = resolve_runtime_dlls(self.game, self.native)
        for name, path in expected.items():
            self.assertEqual(result['platform_stubs'][name], path)
        self.assertFalse(result['missing_platform_stubs'])

    def test_missing_fail_closed_stubs_are_reported(self):
        result = resolve_runtime_dlls(self.game, self.native)
        self.assertEqual(
            set(result['missing_platform_stubs']), set(FAIL_CLOSED_PLATFORM_STUBS))
        self.assertFalse(result['platform_stubs'])


if __name__ == '__main__':
    unittest.main()
