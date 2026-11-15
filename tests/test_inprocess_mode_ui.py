import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "src/tactics_ui/index.html").read_text(encoding="utf-8")
ENGINE_SETTINGS = (ROOT / "src/tactics_ui/engine-settings.js").read_text(encoding="utf-8")
SERVER = (ROOT / "src/fm27_tactics_server.py").read_text(encoding="utf-8")

class InProcessModeUiTests(unittest.TestCase):
    def test_desktop_engine_settings_exposes_both_execution_modes(self):
        self.assertIn('id="engine-mode"', INDEX)
        self.assertIn('value="isolated"', INDEX)
        self.assertIn('value="inprocess"', INDEX)
        self.assertIn('id="engine-mode-apply"', INDEX)

    def test_ui_posts_mode_and_refreshes_status(self):
        self.assertIn("api('/api/engine/mode',{mode:selected})", ENGINE_SETTINGS)
        self.assertIn("showEngineStatus(status)", ENGINE_SETTINGS)
        self.assertIn("NativeWorker Enabled", ENGINE_SETTINGS)
        self.assertIn("workers.value='1';workers.disabled=true", ENGINE_SETTINGS)
        self.assertIn("workers.value=isolatedWorkerCount", ENGINE_SETTINGS)

    def test_backend_persists_mode_and_requires_valid_idle_state(self):
        self.assertIn("if path=='/api/engine/mode':", SERVER)
        self.assertIn("selected not in ('isolated','inprocess')", SERVER)
        self.assertIn("比赛运行中不能更换执行方式", SERVER)
        self.assertIn("native-execution-mode.txt", SERVER)
        self.assertIn("write_text(selected+'\\n',encoding='utf8')", SERVER)

if __name__ == "__main__":
    unittest.main()
