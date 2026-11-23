import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import desktop_engine_acceptance


class EngineAcceptanceTests(unittest.TestCase):
    def test_requires_full_native_match_and_statistics(self):
        payload = {
            "verified": True,
            "result": {"result": {"event": "natural_match_finished",
                                  "full_match_completed": True,
                                  "score": [2, 1], "tick": 1234}},
            "statistics": {"event": "native_match_statistics"},
            "timings": {"event": "native_timings"},
            "engine_compatibility": {"compatible": True},
            "engine_dll_sha256": "abc",
            "elapsed_seconds": 12.5,
        }
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "acceptance"
            with patch.object(desktop_engine_acceptance, "BatchRunner") as runner:
                runner.return_value.one.return_value = payload
                result = desktop_engine_acceptance.run_smoke(Path(temp), output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["match"]["score"], [2, 1])
        self.assertTrue(Path(result["log"]).is_absolute())

    def test_rejects_process_without_native_match_evidence(self):
        payload = {
            "verified": True,
            "result": {"result": {"full_match_completed": True}},
            "statistics": None,
            "timings": {"event": "native_timings"},
        }
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "acceptance"
            with patch.object(desktop_engine_acceptance, "BatchRunner") as runner:
                runner.return_value.one.return_value = payload
                result = desktop_engine_acceptance.run_smoke(Path(temp), output)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "acceptance_evidence")


if __name__ == "__main__":
    unittest.main()
