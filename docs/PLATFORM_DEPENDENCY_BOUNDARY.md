# Local engine and platform API boundary

## What the launcher isolates

FM Tactics Lab starts its own local Python service and native simulation host. It does not start Steam or Epic, read their client registries, search their library folders, or ask them to launch the game. The game root is supplied explicitly, remembered after selection, or selected with a folder picker.

This is an application/launcher boundary. It is not evidence that every function imported by the game engine is independent of platform services.

## Static evidence for the pinned local FM27 binary

The current local reference `game_plugin.dll` is identified by SHA256:

`f79b0a3413dd0e3f461b0afbc3ff397003f4a26d7525a30717428de6a8b91196`

The read-only import/callsite report for that exact image records 46 import descriptors, 806 imported functions, and 159 imports across four platform-related modules:

| Imported module | Imported functions | Direct calls | Jumps | Other IAT references |
|---|---:|---:|---:|---:|
| PartyWin.dll | 20 | 0 | 0 | 0 |
| PlayFabMultiplayerWin.dll | 19 | 0 | 0 | 0 |
| EOSSDK-Win64-Shipping.dll | 109 | 143 | 0 | 8 |
| steam_api64.dll | 11 | 139 | 3 | 3 |

The zero-reference result makes PartyWin and PlayFab Multiplayer candidates for loader-level isolation. It does not prove that runtime-populated function pointers, callbacks, or dynamically resolved symbols can never reach them.

The Steam/EOS call-site counts are substantial. They prevent us from claiming, based on imports alone, that the game engine never uses those APIs.

## Current fail-closed boundary

The native build creates two x64 import stubs for the 20 PartyWin and 19 PlayFab functions. Every unexpected call is logged and terminates the worker. The Steam and EOS diagnostic modules similarly expose the exact imported names and trap unexpected calls.

The probes are not real platform runtimes and are not authentication emulators. They do not return successful initialization, login, account, token, ownership, entitlement, achievement, lobby, or network results. They do not patch the original `game_plugin.dll`, alter its code, or write the engine activation flag.

This design gives the local host a way to identify attempted platform calls without silently manufacturing a successful match. It does **not** make a required platform call disappear. If the local game engine invokes one of the trapped APIs during startup, fixture preparation, or a match, that run must stop and be diagnosed. Do not label a DLL load or fixture setup as a complete match.

## What the current validation proves

Windows CI compiles the C++ host, the PartyWin/PlayFab stubs, and the Steam/EOS diagnostic probes. It verifies PE export tables and checks that statically imported PartyWin/PlayFab functions bind to the expected fail-fast modules.

These checks validate source/build contracts. They do not establish that the user's local game binary can complete a full match without making a platform API call. That still requires a local build using the exact `game_plugin.dll` and a real end-to-end simulation.

## Next runtime evidence

For each local run, retain the native host JSONL log and report:

- whether `game_plugin.dll` loaded;
- whether the engine reached the original initialization path;
- whether `platform_probe_unexpected_call` or `platform_stub_unexpected_call` occurred, including the API name and call stack;
- whether the activation gate changed naturally;
- whether the native match reached its normal end and returned validated results.

A failed platform API call, activation timeout, or match timeout must remain a failure. The host must not fake a platform response or force the activation state to turn it into a nominal success.
