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
these modules by absolute path before loading the unchanged game_plugin.dll.
After load, the host parses the original module's in-memory PE import table and
checks every resolved FirstThunk address for these two descriptors with
VirtualQuery; all 20 PartyWin and 19 PlayFab slots must map to the respective
stub module's allocation base. A simple same-name module lookup is not treated
as sufficient proof of IAT binding.

Every stub export points to one fatal handler. If an unexpected call reaches
one, it appends platform_stub_unexpected_call to the current match log,
writes an OutputDebugString diagnostic, and fail-fast terminates the process.
The stubs never return a success code, token, account, ownership, entitlement,
lobby, or network result.

The genuine ICU, EOS SDK, and Steam runtime dependencies remain required and
are resolved from the known game/bundle directories. In particular, EOS Auth,
EOS Connect, EOS Ecom/ownership, Steam initialization, callbacks, and shutdown
are not stubbed or given fabricated responses.

## Runtime diagnostics

The host records module load paths before and after the existing native
initializer call at RVA 0x9FA910, together with its return value, duration and
thread ID. The initializer is retained unchanged; the event name deliberately
does not label it as a Steam/EOS initializer.

The shared import-table verifier checks the mapped module headers, import descriptor terminator, unique PartyWin/PlayFab descriptors, thunk-table bounds, exact 20/19 counts, and each executable IAT address's owning module. The import-table verification runs immediately after loading game_plugin.dll,
before native activation or match setup. Any count mismatch, unresolved import,
or IAT address outside the expected stub module fails closed with a diagnostic
exit code.

## Validation status

The Windows CI compiles the native host source against a temporary compile-only
compatibility header; the header contains placeholder bytes and is never used
for runtime or packaged output. The same CI compiles both x64 stub DLLs and builds a synthetic importer that
contains the same 39 PartyWin/PlayFab import names. It preloads the two stubs,
loads that importer, and checks all 39 resolved function addresses with
`VirtualQuery`; none of the platform functions are called. The smoke executable runs the same shared PE/IAT verifier used by the actual host, and confirms it rejects swapped PartyWin/PlayFab module identities. The verifier also fails closed on duplicate or missing descriptors and malformed thunk tables. CI also runs
`scripts/verify_platform_stub_exports.py` against the resulting PE files. The
verifier compares actual export-name sets against the pinned original engine
import manifest, checks that all named exports share one fail-fast code
target, and confirms that the only imported runtime module is KERNEL32.dll.

The Python resolver tests cover known directory layouts, split dependencies,
conflicting duplicate DLLs, and bundle-only stub selection. Source-level tests
check the 39 exact manifest exports, fail-fast behavior, and the host IAT guard.
A full native build using the actual local game_plugin.dll and a real local
engine match are still required before this isolation can be considered
validated. Until then, describe it as an experimental
fail-closed loader boundary, not as proof that the two services are unused at
runtime.
