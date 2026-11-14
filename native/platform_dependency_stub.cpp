#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#if defined(BUILD_PARTYWIN_STUB)
#define STUB_MODULE_NAME "PartyWin.dll"
#define STUB_EXIT_CODE 0xE0410001
#pragma comment(linker, "/EXPORT:PartyCleanup=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyConnectToNetwork=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyCreateLocalUser=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyCreateNewNetwork=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyDeserializeNetworkDescriptor=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyDestroyLocalUser=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyEndpointGetEntityId=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyEndpointSendMessage=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyFinishProcessingStateChanges=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyGetErrorMessage=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyGetWorkMode=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyInitialize=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyLocalUserUpdateEntityToken=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyNetworkAuthenticateLocalUser=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyNetworkCreateEndpoint=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyNetworkGetNetworkDescriptor=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyNetworkGetNetworkStatistics=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyNetworkLeaveNetwork=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartySerializeNetworkDescriptor=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PartyStartProcessingStateChanges=PlatformDependencyUnexpectedCall")
#elif defined(BUILD_PLAYFAB_STUB)
#define STUB_MODULE_NAME "PlayFabMultiplayerWin.dll"
#define STUB_EXIT_CODE 0xE0410002
#pragma comment(linker, "/EXPORT:PFLobbyGetConnectionString=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyGetLobbyId=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyGetLobbyProperty=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyGetLobbyPropertyKeys=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyGetMembers=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyGetOwner=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyGetSearchProperty=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyGetSearchPropertyKeys=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyLeave=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFLobbyPostUpdate=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerCreateAndJoinLobby=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerFindLobbies=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerFinishProcessingLobbyStateChanges=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerGetErrorMessage=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerInitialize=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerJoinLobby=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerSetEntityToken=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerStartProcessingLobbyStateChanges=PlatformDependencyUnexpectedCall")
#pragma comment(linker, "/EXPORT:PFMultiplayerUninitialize=PlatformDependencyUnexpectedCall")
#else
#error Select exactly one platform stub with BUILD_PARTYWIN_STUB or BUILD_PLAYFAB_STUB.
#endif

extern "C" __declspec(noreturn) void __cdecl PlatformDependencyUnexpectedCall(void) {
    static const char event[] =
        "{\"event\":\"platform_stub_unexpected_call\",\"module\":\"" STUB_MODULE_NAME "\"}\r\n";
    wchar_t log_path[1024];
    log_path[0] = L'\0';
    DWORD length = GetEnvironmentVariableW(L"FM27_PLATFORM_STUB_LOG", log_path,
                                           static_cast<DWORD>(sizeof(log_path) / sizeof(log_path[0])));
    if (length && length < sizeof(log_path) / sizeof(log_path[0])) {
        HANDLE file = CreateFileW(log_path, FILE_APPEND_DATA,
                                  FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                  nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file != INVALID_HANDLE_VALUE) {
            DWORD written = 0;
            WriteFile(file, event, static_cast<DWORD>(sizeof(event) - 1), &written, nullptr);
            CloseHandle(file);
        }
    }
    OutputDebugStringA(event);
    RaiseFailFastException(nullptr, nullptr, 0);
    TerminateProcess(GetCurrentProcess(), STUB_EXIT_CODE);
    for (;;) {
        Sleep(INFINITE);
    }
}

extern "C" BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) {
    return TRUE;
}
