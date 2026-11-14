# Platform dependency boundary (experimental)

## Static evidence for the reference FM27 build

The checked-in adapter profile identifies the reference game_plugin.dll by
SHA256 f79b0a3413dd0e3f461b0afbc3ff397003f4a26d7525a30717428de6a8b91196.
The read-only import/callsite reports in the maintainer workspace record 46
import descriptors, 806 imported functions, and 159 imports across four
platform modules.

For this exact image hash, the full instruction scan reports:

| Imported module | Imported functions | Direct calls | Jumps | Other IAT references |
|---|---:|---:|---:|---:|
| PartyWin.dll | 20 | 0 | 0 | 0 |
| PlayFabMultiplayerWin.dll | 19 | 0 | 0 | 0 |
| EOSSDK-Win64-Shipping.dll | 109 | 143 | 0 | 8 |
| steam_api64.dll | 11 | 139 | 3 | 3 |

The zero-reference result makes PartyWin and PlayFab Multiplayer candidates
for loader-level isolation. It does not prove that a runtime-populated
function pointer, callback, or dynamically resolved symbol can never reach
them.

## Fail-closed import stubs

The native build creates two small x64 DLLs with the exact 39 statically
imported export names for PartyWin and PlayFab Multiplayer. The host preloads
these modules by absolute path before loading the unchanged game_plugin.dll,
then verifies that Windows still has those exact module handles registered
under the imported names.

Every stub export points to one fatal handler. If an unexpected call reaches
one, it appends platform_stub_unexpected_call to the current match log,
writes an OutputDebugString diagnostic, and fail-fast terminates the process.
The stubs never return a success code, token, account, ownership, entitlement,
lobby, or network result.

The genuine ICU, EOS SDK, and Steam runtime dependencies remain required and
are resolved from the known game/bundle directories. In particular, EOS Auth,
EOS Connect, EOS Ecom/ownership, Steam initialization, callbacks, and shutdown
are not stubbed or given fabricated responses.

## Validation status

The Python resolver tests cover known directory layouts, split dependencies,
conflicting duplicate DLLs, and bundle-only stub selection. A Windows x64 MSVC
build and a real local-engine match are still required before this isolation
can be considered validated. Until then, describe it as an experimental
fail-closed loader boundary, not as proof that the two services are unused at
runtime.
