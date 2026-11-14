import json
import re
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'native' / 'platform_dependency_stub.cpp'
HOST = ROOT / 'native' / 'desktop_host.cpp'
PROFILE = ROOT / 'native' / 'profile_metadata.json'
RUNNER = ROOT / 'scripts' / 'run.py'
VERIFIER = ROOT / 'scripts' / 'verify_platform_stub_exports.py'
IAT_VERIFIER = ROOT / 'native' / 'platform_stub_iat_verifier.h'
SMOKE = ROOT / 'native' / 'platform_stub_loader_smoke.cpp'
BUILD_NATIVE = ROOT / 'scripts' / 'build_native.py'
PROBE_TEMPLATE = ROOT / 'native' / 'platform_probe_stub_template.cpp'
PROBE_BUILDER = ROOT / 'scripts' / 'build_platform_probe_stubs.py'
PROBE_VERIFIER = ROOT / 'scripts' / 'verify_platform_probe_stubs.py'
LIFECYCLE = ROOT / 'native' / 'native_steam_lifecycle.h'

PARTY_EXPORTS = {
    'PartyCleanup',
    'PartyConnectToNetwork',
    'PartyCreateLocalUser',
    'PartyCreateNewNetwork',
    'PartyDeserializeNetworkDescriptor',
    'PartyDestroyLocalUser',
    'PartyEndpointGetEntityId',
    'PartyEndpointSendMessage',
    'PartyFinishProcessingStateChanges',
    'PartyGetErrorMessage',
    'PartyGetWorkMode',
    'PartyInitialize',
    'PartyLocalUserUpdateEntityToken',
    'PartyNetworkAuthenticateLocalUser',
    'PartyNetworkCreateEndpoint',
    'PartyNetworkGetNetworkDescriptor',
    'PartyNetworkGetNetworkStatistics',
    'PartyNetworkLeaveNetwork',
    'PartySerializeNetworkDescriptor',
    'PartyStartProcessingStateChanges',
}

PLAYFAB_EXPORTS = {
    'PFLobbyGetConnectionString',
    'PFLobbyGetLobbyId',
    'PFLobbyGetLobbyProperty',
    'PFLobbyGetLobbyPropertyKeys',
    'PFLobbyGetMembers',
    'PFLobbyGetOwner',
    'PFLobbyGetSearchProperty',
    'PFLobbyGetSearchPropertyKeys',
    'PFLobbyLeave',
    'PFLobbyPostUpdate',
    'PFMultiplayerCreateAndJoinLobby',
    'PFMultiplayerFindLobbies',
    'PFMultiplayerFinishProcessingLobbyStateChanges',
    'PFMultiplayerGetErrorMessage',
    'PFMultiplayerInitialize',
    'PFMultiplayerJoinLobby',
    'PFMultiplayerSetEntityToken',
    'PFMultiplayerStartProcessingLobbyStateChanges',
    'PFMultiplayerUninitialize',
}


class PlatformProbeBuilderTests(unittest.TestCase):
    def test_probe_manifest_covers_exact_steam_and_eos_imports(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        from build_platform_probe_stubs import MODULES, imports_for
        metadata = json.loads(PROFILE.read_text(encoding='utf-8'))
        self.assertEqual(len(imports_for(metadata, 'steam_api64.dll')), 11)
        self.assertEqual(len(imports_for(metadata, 'eossdk-win64-shipping.dll')), 109)
        self.assertEqual(
            {name for name in MODULES},
            {'steam_api64.dll', 'EOSSDK-Win64-Shipping.dll'})

    def test_each_platform_import_gets_a_named_fail_fast_wrapper(self):
        template = PROBE_TEMPLATE.read_text(encoding='utf-8')
        builder = PROBE_BUILDER.read_text(encoding='utf-8')
        verifier = PROBE_VERIFIER.read_text(encoding='utf-8')
        self.assertIn('DEFINE_PLATFORM_PROBE({name})', builder)
        self.assertIn('Probe_{name}', builder)
        self.assertIn('platform_probe_unexpected_call', template)
        self.assertIn('CaptureStackBackTrace', template)
        self.assertIn('engine_rva', template)
        self.assertIn('RaiseFailFastException', template)
        self.assertIn('distinct_api_traps', verifier)
        self.assertIn('kernel32.dll', verifier)
        self.assertNotIn('return 0;', template)


class PlatformStubBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf-8')

    def test_exact_partywin_import_exports_are_present(self):
        exports = set(re.findall(
            r'/EXPORT:([A-Za-z0-9_]+)=PlatformDependencyUnexpectedCall',
            self.source.split('#elif defined(BUILD_PLAYFAB_STUB)')[0]))
        self.assertEqual(exports, PARTY_EXPORTS)

    def test_stub_exports_match_the_checked_in_engine_import_manifest(self):
        profile = json.loads(PROFILE.read_text(encoding='utf-8'))
        imports = profile['imports']
        expected = {
            'partywin.dll': {
                row['name'] for row in imports
                if row['dll'].lower() == 'partywin.dll'
            },
            'playfabmultiplayerwin.dll': {
                row['name'] for row in imports
                if row['dll'].lower() == 'playfabmultiplayerwin.dll'
            },
        }
        self.assertEqual(expected['partywin.dll'], PARTY_EXPORTS)
        self.assertEqual(expected['playfabmultiplayerwin.dll'], PLAYFAB_EXPORTS)
        self.assertEqual(len(PARTY_EXPORTS) + len(PLAYFAB_EXPORTS), 39)

    def test_exact_playfab_import_exports_are_present(self):
        section = self.source.split('#elif defined(BUILD_PLAYFAB_STUB)', 1)[1]
        section = section.split('#else', 1)[0]
        exports = set(re.findall(
            r'/EXPORT:([A-Za-z0-9_]+)=PlatformDependencyUnexpectedCall', section))
        self.assertEqual(exports, PLAYFAB_EXPORTS)

    def test_unexpected_platform_calls_fail_fast_without_success_returns(self):
        self.assertIn('__declspec(noreturn)', self.source)
        self.assertIn('RaiseFailFastException', self.source)
        self.assertIn('TerminateProcess', self.source)
        self.assertIn('platform_stub_unexpected_call', self.source)
        handler = self.source.split('PlatformDependencyUnexpectedCall(void)', 1)[1]
        handler = handler.split('extern "C" BOOL WINAPI DllMain', 1)[0]
        self.assertNotRegex(handler, r'\breturn\s+')


class PlatformStubHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = HOST.read_text(encoding='utf-8')

    def test_import_address_table_is_verified_against_stub_module(self):
        verifier = IAT_VERIFIER.read_text(encoding='utf-8')
        self.assertIn('desktop_verify_platform_stub_iat()', self.host)
        self.assertIn('fm27_platform_boundary::verify_imports', self.host)
        self.assertIn('VirtualQuery(address, &memory, sizeof(memory))', verifier)
        self.assertIn('memory.AllocationBase != module', verifier)
        self.assertIn('IatError::duplicate_descriptor', verifier)
        self.assertIn('IatError::iat_target_mismatch', verifier)
        self.assertIn('IatError::missing_descriptor_terminator', verifier)
        self.assertNotIn('module_range_readable(imported_module, image, image_size)', verifier)
        self.assertIn('Every structure and thunk we actually read is checked separately', verifier)


    def test_windows_smoke_executes_the_same_iat_verifier_as_the_host(self):
        smoke = SMOKE.read_text(encoding='utf-8')
        verifier = IAT_VERIFIER.read_text(encoding='utf-8')
        self.assertIn('#include "platform_stub_iat_verifier.h"', self.host)
        self.assertIn('#include "platform_stub_iat_verifier.h"', smoke)
        self.assertIn('verify_imports(fixture, party, playfab)', smoke)
        self.assertIn('IatError::iat_target_mismatch', smoke)
        self.assertIn('duplicate_descriptor', verifier)
        self.assertIn('missing_import_descriptor', verifier)

    def test_native_initializer_is_preserved_and_labelled_neutrally(self):
        self.assertIn('at(0x9fa910))(3)', self.host)
        self.assertIn('native_initializer_gate_result', self.host)
        self.assertIn('before_native_initializer', self.host)
        self.assertIn('after_native_initializer', self.host)
        self.assertNotIn('native_platform_initialized', self.host)

    def test_activation_gate_emits_sampled_state_and_exception_context(self):
        self.assertIn('native_activation_gate_initial', self.host)
        self.assertIn('native_activation_gate_sample', self.host)
        self.assertIn('single_step_exceptions', self.host)
        self.assertIn('cpp_exceptions', self.host)
        self.assertIn('exception_context', self.host)
        self.assertIn('RtlLookupFunctionEntry', self.host)
        self.assertIn('RtlVirtualUnwind', self.host)

    def test_activation_scan_is_read_only_and_targets_the_section_containing_the_gate(self):
        self.assertIn('arg==L"--find-activation"', self.host)
        self.assertIn('if(desktop_find_activation)return scan_activation', self.host)
        scanner = self.host.split('static int scan_activation', 1)[1].split('static int child', 1)[0]
        self.assertIn('configured_gate_rva=0x1718f818', scanner)
        self.assertIn('configured_gate_rva>=section.VirtualAddress', scanner)
        self.assertIn('gate_section=&section', scanner)
        self.assertIn('scan_radius=0x100000', scanner)
        self.assertIn('ReadProcessMemory(GetCurrentProcess()', scanner)
        self.assertIn('memory_modified\\":false', scanner)
        self.assertNotIn('.00cfg', scanner)
        self.assertNotIn('WriteProcessMemory', scanner)
        self.assertNotIn('VirtualProtect', scanner)

    def test_probe_mode_replaces_steam_eos_without_supplying_success(self):
        self.assertIn('FM27_PLATFORM_PROBE_MODE', self.host)
        self.assertIn('desktop_load_platform_probe', self.host)
        self.assertIn('desktop_verify_platform_probe_iat', self.host)
        self.assertIn('verify_named_imports', self.host)
        self.assertIn('steam_login_required\\":false', self.host)
        self.assertIn('platform_success_faked\\":false', self.host)
        lifecycle = LIFECYCLE.read_text(encoding='utf-8')
        self.assertIn('desktop_platform_probe_mode', lifecycle)
        self.assertIn('steam_session_cleanup_skipped', lifecycle)

    def test_probe_mode_is_opt_in_from_source_runner(self):
        runner = RUNNER.read_text(encoding='utf-8')
        self.assertIn('--platform-probe-mode', runner)
        self.assertIn('FM27_PLATFORM_PROBE_MODE', runner)
        resolver = (ROOT / 'src' / 'runtime_layout.py').read_text(encoding='utf-8')
        self.assertIn('PLATFORM_PROBE_DLLS', resolver)
        self.assertIn('missing_platform_probes', resolver)

    def test_source_runner_checks_built_stubs_before_startup(self):
        runner = RUNNER.read_text(encoding='utf-8')
        self.assertIn('platform-stubs/PartyWin.dll', runner)
        self.assertIn('platform-stubs/PlayFabMultiplayerWin.dll', runner)

    def test_binary_verifier_checks_manifest_exports_and_kernel32_only(self):
        verifier = VERIFIER.read_text(encoding='utf-8')
        self.assertIn('actual_names != expected', verifier)
        self.assertIn("imported_dlls != ['kernel32.dll']", verifier)
        self.assertIn('len(set(actual[\'named_function_rvas\'])) != 1', verifier)

    def test_native_builder_checks_the_real_reference_and_built_stub_pes(self):
        build = BUILD_NATIVE.read_text(encoding='utf-8')
        self.assertIn("'--check-image'", build)
        self.assertIn('verify_platform_stub_exports.py', build)
        self.assertIn('build_platform_probe_stubs.py', build)
        self.assertIn("validation.get('disposition') == 'blocked'", build)


if __name__ == '__main__':
    unittest.main()
