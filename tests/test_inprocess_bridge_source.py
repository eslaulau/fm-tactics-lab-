import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "native/desktop_host.cpp").read_text(encoding="utf-8")
LIFECYCLE = (ROOT / "native/native_steam_lifecycle.h").read_text(encoding="utf-8")
EXPORTS = (ROOT / "native/inprocess_bridge_exports.cpp").read_text(encoding="utf-8")
PLUGIN = (ROOT / "integration/BepInEx/FMTL.NativeBridge/NativeBridgePlugin.cs").read_text(encoding="utf-8")
BUILDER = (ROOT / "scripts/build_native.py").read_text(encoding="utf-8")
EXPORTER = (ROOT / "scripts/export_source.py").read_text(encoding="utf-8")
RUNNER = (ROOT / "scripts/run.py").read_text(encoding="utf-8")


class InProcessBridgeSourceTests(unittest.TestCase):
    def test_standalone_entrypoint_is_excluded_from_dll_build(self):
        self.assertIn("#ifndef FM27_INPROCESS_DLL", HOST)
        self.assertIn("#endif // FM27_INPROCESS_DLL", HOST)

    def test_in_process_abort_never_terminates_the_game_process(self):
        self.assertIn("if(desktop_in_process_mode)throw desktop_worker_abort{code};", LIFECYCLE)
        self.assertIn("InterlockedCompareExchange(&desktop_in_process_cancel_requested", LIFECYCLE)
        self.assertIn("FM27InProcessCancel", EXPORTS)
        self.assertNotIn("SteamAPI_Shutdown", EXPORTS)

    def test_game_owned_interface_is_borrowed_not_released(self):
        self.assertIn("if(!desktop_in_process_mode)", HOST)
        self.assertIn("game_interface_released", HOST)
        self.assertIn("desktop_tls_value_guard", HOST)
        self.assertIn("tls_context_restored", HOST)

    def test_readiness_requires_real_fm_runtime_and_initialized_globals(self):
        for name in ("fm.exe", "UnityPlayer.dll", "GameAssembly.dll", "game_plugin.dll",
                     "steam_api64.dll", "steamclient64.dll", "EOSSDK-Win64-Shipping.dll"):
            self.assertIn(name, EXPORTS)
        for address in ("0x0580EA08", "0x0580ED90", "0x0580EC60",
                        "0x0580EB40", "0x0581CAB0", "0x0580E7B8"):
            self.assertIn(address, EXPORTS)
        self.assertIn("activation_gate", EXPORTS)

    def test_exports_and_plugin_protocol_match(self):
        for name in ("FM27InProcessAbiVersion", "FM27InProcessCheckReady",
                     "FM27InProcessRunManifest", "FM27InProcessCancel"):
            self.assertIn(name, EXPORTS)
        for endpoint in ('"/health"', '"/run"', '"/status"', '"/cancel"'):
            self.assertIn(endpoint, PLUGIN)
        self.assertIn("NativeLibrary.Load", PLUGIN)
        self.assertIn("NativeWorker\", \"Enabled\", false", PLUGIN)
        self.assertIn("X-FMTL-Token", PLUGIN)
        self.assertIn("localhost", PLUGIN)

    def test_runner_requires_genuine_sdk_and_adapter_specific_bridge(self):
        self.assertIn("--execution-mode", RUNNER)
        self.assertIn("FM27_NATIVE_EXECUTION_MODE=args.execution_mode", RUNNER)
        self.assertIn("--platform-api-mode genuine", RUNNER)
        self.assertIn("adapter_root / 'FM27InProcessNative.dll'", RUNNER)

    def test_build_and_source_export_include_bridge(self):
        self.assertIn("FM27InProcessNative.dll", BUILDER)
        self.assertIn("inprocess_bridge_exports.cpp", BUILDER)
        self.assertIn("'integration': {'.cs', '.csproj'}", EXPORTER)


if __name__ == "__main__":
    unittest.main()
