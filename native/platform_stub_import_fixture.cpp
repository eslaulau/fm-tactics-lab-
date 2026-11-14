#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

extern "C" __declspec(dllimport) void __cdecl PartyCleanup(void);
extern "C" __declspec(dllimport) void __cdecl PartyConnectToNetwork(void);
extern "C" __declspec(dllimport) void __cdecl PartyCreateLocalUser(void);
extern "C" __declspec(dllimport) void __cdecl PartyCreateNewNetwork(void);
extern "C" __declspec(dllimport) void __cdecl PartyDeserializeNetworkDescriptor(void);
extern "C" __declspec(dllimport) void __cdecl PartyDestroyLocalUser(void);
extern "C" __declspec(dllimport) void __cdecl PartyEndpointGetEntityId(void);
extern "C" __declspec(dllimport) void __cdecl PartyEndpointSendMessage(void);
extern "C" __declspec(dllimport) void __cdecl PartyFinishProcessingStateChanges(void);
extern "C" __declspec(dllimport) void __cdecl PartyGetErrorMessage(void);
extern "C" __declspec(dllimport) void __cdecl PartyGetWorkMode(void);
extern "C" __declspec(dllimport) void __cdecl PartyInitialize(void);
extern "C" __declspec(dllimport) void __cdecl PartyLocalUserUpdateEntityToken(void);
extern "C" __declspec(dllimport) void __cdecl PartyNetworkAuthenticateLocalUser(void);
extern "C" __declspec(dllimport) void __cdecl PartyNetworkCreateEndpoint(void);
extern "C" __declspec(dllimport) void __cdecl PartyNetworkGetNetworkDescriptor(void);
extern "C" __declspec(dllimport) void __cdecl PartyNetworkGetNetworkStatistics(void);
extern "C" __declspec(dllimport) void __cdecl PartyNetworkLeaveNetwork(void);
extern "C" __declspec(dllimport) void __cdecl PartySerializeNetworkDescriptor(void);
extern "C" __declspec(dllimport) void __cdecl PartyStartProcessingStateChanges(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetConnectionString(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetLobbyId(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetLobbyProperty(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetLobbyPropertyKeys(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetMembers(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetOwner(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetSearchProperty(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyGetSearchPropertyKeys(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyLeave(void);
extern "C" __declspec(dllimport) void __cdecl PFLobbyPostUpdate(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerCreateAndJoinLobby(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerFindLobbies(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerFinishProcessingLobbyStateChanges(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerGetErrorMessage(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerInitialize(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerJoinLobby(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerSetEntityToken(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerStartProcessingLobbyStateChanges(void);
extern "C" __declspec(dllimport) void __cdecl PFMultiplayerUninitialize(void);

static const void* const imported_addresses[] = {
    reinterpret_cast<const void*>(&PartyCleanup),
    reinterpret_cast<const void*>(&PartyConnectToNetwork),
    reinterpret_cast<const void*>(&PartyCreateLocalUser),
    reinterpret_cast<const void*>(&PartyCreateNewNetwork),
    reinterpret_cast<const void*>(&PartyDeserializeNetworkDescriptor),
    reinterpret_cast<const void*>(&PartyDestroyLocalUser),
    reinterpret_cast<const void*>(&PartyEndpointGetEntityId),
    reinterpret_cast<const void*>(&PartyEndpointSendMessage),
    reinterpret_cast<const void*>(&PartyFinishProcessingStateChanges),
    reinterpret_cast<const void*>(&PartyGetErrorMessage),
    reinterpret_cast<const void*>(&PartyGetWorkMode),
    reinterpret_cast<const void*>(&PartyInitialize),
    reinterpret_cast<const void*>(&PartyLocalUserUpdateEntityToken),
    reinterpret_cast<const void*>(&PartyNetworkAuthenticateLocalUser),
    reinterpret_cast<const void*>(&PartyNetworkCreateEndpoint),
    reinterpret_cast<const void*>(&PartyNetworkGetNetworkDescriptor),
    reinterpret_cast<const void*>(&PartyNetworkGetNetworkStatistics),
    reinterpret_cast<const void*>(&PartyNetworkLeaveNetwork),
    reinterpret_cast<const void*>(&PartySerializeNetworkDescriptor),
    reinterpret_cast<const void*>(&PartyStartProcessingStateChanges),
    reinterpret_cast<const void*>(&PFLobbyGetConnectionString),
    reinterpret_cast<const void*>(&PFLobbyGetLobbyId),
    reinterpret_cast<const void*>(&PFLobbyGetLobbyProperty),
    reinterpret_cast<const void*>(&PFLobbyGetLobbyPropertyKeys),
    reinterpret_cast<const void*>(&PFLobbyGetMembers),
    reinterpret_cast<const void*>(&PFLobbyGetOwner),
    reinterpret_cast<const void*>(&PFLobbyGetSearchProperty),
    reinterpret_cast<const void*>(&PFLobbyGetSearchPropertyKeys),
    reinterpret_cast<const void*>(&PFLobbyLeave),
    reinterpret_cast<const void*>(&PFLobbyPostUpdate),
    reinterpret_cast<const void*>(&PFMultiplayerCreateAndJoinLobby),
    reinterpret_cast<const void*>(&PFMultiplayerFindLobbies),
    reinterpret_cast<const void*>(&PFMultiplayerFinishProcessingLobbyStateChanges),
    reinterpret_cast<const void*>(&PFMultiplayerGetErrorMessage),
    reinterpret_cast<const void*>(&PFMultiplayerInitialize),
    reinterpret_cast<const void*>(&PFMultiplayerJoinLobby),
    reinterpret_cast<const void*>(&PFMultiplayerSetEntityToken),
    reinterpret_cast<const void*>(&PFMultiplayerStartProcessingLobbyStateChanges),
    reinterpret_cast<const void*>(&PFMultiplayerUninitialize)
};

extern "C" __declspec(dllexport)
const void* const* __cdecl GetFixtureImportedAddresses(unsigned* count) {
    if (count) {
        *count = static_cast<unsigned>(
            sizeof(imported_addresses) / sizeof(imported_addresses[0]));
    }
    return imported_addresses;
}

extern "C" BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) {
    return TRUE;
}
