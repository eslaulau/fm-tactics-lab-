import json
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'native' / 'platform_dependency_stub.cpp'
HOST = ROOT / 'native' / 'desktop_host.cpp'
PROFILE = ROOT / 'native' / 'profile_metadata.json'
RUNNER = ROOT / 'scripts' / 'run.py'
VERIFIER = ROOT / 'scripts' / 'verify_platform_stub_exports.py'
BUILD_NATIVE = ROOT / 'scripts' / 'build_native.py'

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
        self.assertIn('desktop_verify_platform_stub_iat()', self.host)
        self.assertIn('VirtualQuery(address,&memory,sizeof(memory))', self.host)
        self.assertIn('memory.AllocationBase!=expected', self.host)
        self.assertIn('expected_count=target==0?20:19', self.host)
        self.assertIn('observed[0]!=20||observed[1]!=19', self.host)

    def test_native_initializer_is_preserved_and_labelled_neutrally(self):
        self.assertIn('at(0x9fa910))(3)', self.host)
        self.assertIn('native_initializer_gate_result', self.host)
        self.assertIn('before_native_initializer', self.host)
        self.assertIn('after_native_initializer', self.host)
        self.assertNotIn('native_platform_initialized', self.host)

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
        self.assertIn("validation.get('disposition') == 'blocked'", build)


if __name__ == '__main__':
    unittest.main()
