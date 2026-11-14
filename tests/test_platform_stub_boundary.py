import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'native' / 'platform_dependency_stub.cpp'

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


if __name__ == '__main__':
    unittest.main()
