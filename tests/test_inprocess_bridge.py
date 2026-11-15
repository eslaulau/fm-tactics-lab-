import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import inprocess_bridge as bridge


class FakeClient:
    def __init__(self, status=None, run=None, failure=None):
        self.status = status or {"ok": True, "jobId": "job-1", "status": "running"}
        self.run = run or {"ok": True, "jobId": "job-1", "status": "running"}
        self.failure = failure
        self.requests = []

    def health(self):
        return {"ok": True, "nativeWorkerEnabled": True, "gameRoot": "C:/FM27"}

    def request(self, path, method="GET", body=None, timeout=5):
        self.requests.append((path, method, body))
        if self.failure:
            raise self.failure
        if path == "/run":
            return self.run
        if path.startswith("/status"):
            return self.status
        if path == "/cancel":
            return {"ok": True, "cancelRequested": True}
        raise AssertionError(path)


class InProcessBridgeTests(unittest.TestCase):
    def test_reads_token_and_port_from_bepinex_config(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "BepInEx" / "config"
            config.mkdir(parents=True)
            token = "a" * 64
            path = config / (bridge.PLUGIN_ID + ".cfg")
            path.write_text(
                "[Bridge]\nPort = 5133\nToken = " + token + "\n"
                "[NativeWorker]\nEnabled = true\n",
                encoding="utf-8"
            )
            self.assertEqual(bridge._read_bridge_config(folder), (5133, token))

    def test_client_uses_the_listener_localhost_name_and_disables_proxies(self):
        client = bridge._BridgeClient("C:/FM27")
        self.assertEqual(client.base_url, f"http://localhost:{client.port}")
        self.assertIsInstance(client.opener, type(bridge.urllib.request.build_opener(
            bridge.urllib.request.ProxyHandler({})
        )))

    def test_job_poll_translates_completed_bridge_job(self):
        fake = FakeClient(status={
            "ok": True, "jobId": "job-1", "status": "completed",
            "returnCode": 0, "result": "{\"ok\":true}"
        })
        with patch.object(bridge, "_BridgeClient", return_value=fake):
            process = bridge.InProcessBridgeProcess(
                "C:/FM27", "C:/Engine", "C:/Run/manifest.txt", "C:/Run/session.jsonl"
            )
            with patch.object(bridge.time, "monotonic", return_value=1.0):
                self.assertEqual(process.poll(), 0)
            self.assertEqual(process.communicate()[0], b"{\"ok\":true}")

    def test_job_poll_turns_disconnect_into_nonzero_exit(self):
        fake = FakeClient(failure=RuntimeError("FM27 closed"))
        with patch.object(bridge, "_BridgeClient", return_value=fake):
            process = bridge.InProcessBridgeProcess(
                "C:/FM27", "C:/Engine", "C:/Run/manifest.txt", "C:/Run/session.jsonl"
            )
            with patch.object(bridge.time, "monotonic", return_value=1.0):
                self.assertEqual(process.poll(), 255)
            self.assertIn(b"unreachable", process.communicate()[0])

    def test_cancel_posts_only_to_local_bridge(self):
        fake = FakeClient()
        with patch.object(bridge, "_BridgeClient", return_value=fake):
            cancellation = bridge.InProcessCancellation("C:/FM27")
            cancellation.signal()
            self.assertEqual(fake.requests[-1][0], "/cancel")
            self.assertEqual(fake.requests[-1][1], "POST")


if __name__ == "__main__":
    unittest.main()
