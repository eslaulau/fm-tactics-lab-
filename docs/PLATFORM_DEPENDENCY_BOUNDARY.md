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

In normal mode, the genuine ICU, EOS SDK, and Steam runtime dependencies remain
required and are resolved from the known game/bundle directories. In
particular, EOS Auth, EOS Connect, EOS Ecom/ownership, Steam initialization,
callbacks, and shutdown are not given fabricated responses.

## No-login diagnostic probe mode

The build now also generates opt-in diagnostic replacements for the 11 Steam
and 109 EOS imports from the pinned manifest. Unlike the PartyWin/PlayFab
boundary, these probes are deliberately **not** enabled in normal runs.

Set `FM27_PLATFORM_PROBE_MODE=1` for a direct native-host diagnostic, or launch
the source runner with `--platform-probe-mode`. In this mode the host does not
require or load the genuine Steam/EOS runtime DLLs, does not set Steam app-ID
environment metadata, and skips the Steam shutdown hook. It preloads the
API-identifying probes by absolute path and verifies every Steam/EOS IAT slot
belongs to the expected probe module before continuing.

Each imported API has a distinct fail-fast entry point. If the native engine
calls one, the probe writes `platform_probe_unexpected_call` with the exact API
name and a captured call stack (including an engine RVA when the frame lies
inside `game_plugin.dll`), then terminates. It never returns an invented
success result, token, login state, ownership or entitlement.

This mode is an investigation tool, not yet a supported production runtime.
A probe hit identifies an actual platform call that must be understood and
isolated safely; a clean zero-tick fixture preparation only establishes that
the engine reached that point without calling the probed APIs. It does not by
itself prove that a complete match can run without platform services.

### Local no-login diagnostic procedure

Build from an x64 Visual Studio Native Tools shell with the exact local FM27
reference DLL:

```powershell
py -3.12 scripts\build_native.py --reference-dll "D:\Games\Football Manager 27\fm_Data\Plugins\x86_64\game_plugin.dll"
```

Then, with no FM client or Steam session running, use this zero-tick fixture
preparation check:

```powershell
$env:FM27_ENGINE_ROOT = (Resolve-Path ".\private\engine").Path
$env:FM27_GAME_ROOT = "D:\Games\Football Manager 27"
$env:FM27_PLATFORM_PROBE_MODE = "1"
& ".\private\engine\fm27_native\FM27Simulator.exe" --inspect-fixture
$LASTEXITCODE
Get-Content ".\private\engine\fm27_native\last_match.jsonl" -Tail 80
```

An API call appears as `platform_probe_unexpected_call` with the specific
import name and captured call stack. A `native_fixture_inspected` record with
exit code 0 means fixture preparation reached its inspection point without
calling any probed Steam/EOS imports during that run; no simulation ticks
were executed. Neither outcome should be described as a full match test.

## Runtime diagnostics

The host records module load paths before and after the existing native
initializer call at RVA 0x9FA910, together with its return value, duration and
thread ID. The initializer is retained unchanged; the event name deliberately
does not label it as a Steam/EOS initializer.

The shared import-table verifier checks the mapped module headers, import descriptor terminator, unique PartyWin/PlayFab descriptors, thunk-table bounds, exact 20/19 counts, and each executable IAT address's owning module. It checks only the PE regions it reads rather than assuming the entire `SizeOfImage` range is uniformly readable. The import-table verification runs immediately after loading game_plugin.dll,
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
conflicting duplicate DLLs, bundle-only stubs, and the optional no-login probe
layout. Windows CI compiles and verifies the 11 Steam and 109 EOS named probe
exports, including distinct trap targets and KERNEL32-only dependencies.
Source-level tests check fail-fast behavior, the host IAT guards, and the
no-login mode's environment and cleanup boundaries.
A full native build using the actual local game_plugin.dll and a real local
engine match are still required before this isolation can be considered
validated. Until then, describe it as an experimental
fail-closed loader boundary, not as proof that the two services are unused at
runtime.
