#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <stdio.h>
#include "platform_stub_iat_verifier.h"

using GetFixtureImportedAddressesFn = const void* const* (__cdecl*)(unsigned*);

static int fail(const wchar_t* message, DWORD error = 0) {
    fwprintf(stderr, L"FAIL: %ls (error=%lu)\n", message, error);
    return 1;
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 4) return fail(L"expected PartyWin, PlayFab, and fixture DLL paths");

    HMODULE party = LoadLibraryExW(
        argv[1], nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!party) return fail(L"could not preload PartyWin stub", GetLastError());
    HMODULE playfab = LoadLibraryExW(
        argv[2], nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!playfab) return fail(L"could not preload PlayFab stub", GetLastError());

    if (GetModuleHandleW(L"PartyWin.dll") != party)
        return fail(L"PartyWin module name did not resolve to the preloaded handle");
    if (GetModuleHandleW(L"PlayFabMultiplayerWin.dll") != playfab)
        return fail(L"PlayFab module name did not resolve to the preloaded handle");

    HMODULE fixture = LoadLibraryExW(
        argv[3], nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!fixture) return fail(L"could not load the fixture importer", GetLastError());

    const auto verified = fm27_platform_boundary::verify_imports(fixture, party, playfab);
    if (!verified.ok()) {
        fwprintf(stderr, L"FAIL: shared IAT verifier rejected the importer (reason=%S, module=%d, index=%zu)\n",
                 fm27_platform_boundary::error_name(verified.error),
                 verified.target, verified.index);
        return 2;
    }
    if (verified.party_imports != 20 || verified.playfab_imports != 19)
        return fail(L"shared IAT verifier returned an unexpected import count");

    const auto swapped = fm27_platform_boundary::verify_imports(fixture, playfab, party);
    if (swapped.error != fm27_platform_boundary::IatError::iat_target_mismatch)
        return fail(L"shared IAT verifier did not reject swapped stub-module identities");

    const auto null_module = fm27_platform_boundary::verify_imports(nullptr, party, playfab);
    if (null_module.error != fm27_platform_boundary::IatError::invalid_module)
        return fail(L"shared IAT verifier did not reject a null importer module");

    auto get_addresses = reinterpret_cast<GetFixtureImportedAddressesFn>(
        GetProcAddress(fixture, "GetFixtureImportedAddresses"));
    if (!get_addresses) return fail(L"fixture export was not found", GetLastError());

    unsigned count = 0;
    const void* const* addresses = get_addresses(&count);
    if (!addresses || count != 39) return fail(L"fixture did not expose all 39 imported addresses");

    for (unsigned index = 0; index < count; ++index) {
        MEMORY_BASIC_INFORMATION memory = {};
        if (!addresses[index] ||
            !VirtualQuery(addresses[index], &memory, sizeof(memory))) {
            return fail(L"could not query an imported function address", GetLastError());
        }
        HMODULE expected = index < 20 ? party : playfab;
        if (memory.AllocationBase != expected) {
            fwprintf(stderr, L"FAIL: IAT address %u belongs to %p; expected %p\n",
                     index, memory.AllocationBase, expected);
            return 3;
        }
    }

    wprintf(L"PASS: the shared host IAT verifier accepted all 20 PartyWin and 19 PlayFab imports, and rejected swapped module identities.\n");
    FreeLibrary(fixture);
    FreeLibrary(playfab);
    FreeLibrary(party);
    return 0;
}
