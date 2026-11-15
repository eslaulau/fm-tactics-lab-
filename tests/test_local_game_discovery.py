from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'Launcher.cs'


class LocalGameDiscoveryTests(unittest.TestCase):
    def test_desktop_launcher_uses_explicit_saved_or_selected_game_roots(self):
        source = LAUNCHER.read_text(encoding='utf-8')
        method = source.split('static string FindGame(string[] args){', 1)[1].split(
            'static string Unpack(){', 1)[0]
        self.assertIn('GetArg(args,"--game-root")', method)
        self.assertIn('Environment.GetEnvironmentVariable("FM27_GAME_ROOT")', method)
        self.assertIn('game-root.txt', method)
        self.assertIn('FolderBrowserDialog', method)
        self.assertNotIn('HKEY_CURRENT_USER', method)
        self.assertNotIn('SteamPath', method)
        self.assertNotIn('steamapps', method)
        self.assertNotIn('SteamLibrary', method)

    def test_launcher_does_not_start_a_storefront_client(self):
        source = LAUNCHER.read_text(encoding='utf-8').lower()
        self.assertNotIn('steam.exe', source)
        self.assertNotIn('epicgameslauncher.exe', source)


if __name__ == '__main__':
    unittest.main()
