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

// Filled on demand so the fixture has no CRT-dependent static initializer.
static const void* imported_addresses[39] = {};

extern "C" __declspec(dllexport)
const void* const* __cdecl GetFixtureImportedAddresses(unsigned* count) {
    imported_addresses[0] = reinterpret_cast<const void*>(&PartyCleanup);
    imported_addresses[1] = reinterpret_cast<const void*>(&PartyConnectToNetwork);
    imported_addresses[2] = reinterpret_cast<const void*>(&PartyCreateLocalUser);
    imported_addresses[3] = reinterpret_cast<const void*>(&PartyCreateNewNetwork);
    imported_addresses[4] = reinterpret_cast<const void*>(&PartyDeserializeNetworkDescriptor);
    imported_addresses[5] = reinterpret_cast<const void*>(&PartyDestroyLocalUser);
    imported_addresses[6] = reinterpret_cast<const void*>(&PartyEndpointGetEntityId);
    imported_addresses[7] = reinterpret_cast<const void*>(&PartyEndpointSendMessage);
    imported_addresses[8] = reinterpret_cast<const void*>(&PartyFinishProcessingStateChanges);
    imported_addresses[9] = reinterpret_cast<const void*>(&PartyGetErrorMessage);
    imported_addresses[10] = reinterpret_cast<const void*>(&PartyGetWorkMode);
    imported_addresses[11] = reinterpret_cast<const void*>(&PartyInitialize);
    imported_addresses[12] = reinterpret_cast<const void*>(&PartyLocalUserUpdateEntityToken);
    imported_addresses[13] = reinterpret_cast<const void*>(&PartyNetworkAuthenticateLocalUser);
    imported_addresses[14] = reinterpret_cast<const void*>(&PartyNetworkCreateEndpoint);
    imported_addresses[15] = reinterpret_cast<const void*>(&PartyNetworkGetNetworkDescriptor);
    imported_addresses[16] = reinterpret_cast<const void*>(&PartyNetworkGetNetworkStatistics);
    imported_addresses[17] = reinterpret_cast<const void*>(&PartyNetworkLeaveNetwork);
    imported_addresses[18] = reinterpret_cast<const void*>(&PartySerializeNetworkDescriptor);
    imported_addresses[19] = reinterpret_cast<const void*>(&PartyStartProcessingStateChanges);
    imported_addresses[20] = reinterpret_cast<const void*>(&PFLobbyGetConnectionString);
    imported_addresses[21] = reinterpret_cast<const void*>(&PFLobbyGetLobbyId);
    imported_addresses[22] = reinterpret_cast<const void*>(&PFLobbyGetLobbyProperty);
    imported_addresses[23] = reinterpret_cast<const void*>(&PFLobbyGetLobbyPropertyKeys);
    imported_addresses[24] = reinterpret_cast<const void*>(&PFLobbyGetMembers);
    imported_addresses[25] = reinterpret_cast<const void*>(&PFLobbyGetOwner);
    imported_addresses[26] = reinterpret_cast<const void*>(&PFLobbyGetSearchProperty);
    imported_addresses[27] = reinterpret_cast<const void*>(&PFLobbyGetSearchPropertyKeys);
    imported_addresses[28] = reinterpret_cast<const void*>(&PFLobbyLeave);
    imported_addresses[29] = reinterpret_cast<const void*>(&PFLobbyPostUpdate);
    imported_addresses[30] = reinterpret_cast<const void*>(&PFMultiplayerCreateAndJoinLobby);
    imported_addresses[31] = reinterpret_cast<const void*>(&PFMultiplayerFindLobbies);
    imported_addresses[32] = reinterpret_cast<const void*>(&PFMultiplayerFinishProcessingLobbyStateChanges);
    imported_addresses[33] = reinterpret_cast<const void*>(&PFMultiplayerGetErrorMessage);
    imported_addresses[34] = reinterpret_cast<const void*>(&PFMultiplayerInitialize);
    imported_addresses[35] = reinterpret_cast<const void*>(&PFMultiplayerJoinLobby);
    imported_addresses[36] = reinterpret_cast<const void*>(&PFMultiplayerSetEntityToken);
    imported_addresses[37] = reinterpret_cast<const void*>(&PFMultiplayerStartProcessingLobbyStateChanges);
    imported_addresses[38] = reinterpret_cast<const void*>(&PFMultiplayerUninitialize);
    if (count) *count = static_cast<unsigned>(sizeof(imported_addresses) / sizeof(imported_addresses[0]));
    return imported_addresses;
}

extern "C" BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) {
    return TRUE;
}
