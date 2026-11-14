# Building FM Tactics Lab v1108.5

This source includes the career-save reader and same-league match mode shipped in v1108.5.

## Requirements

- Windows x64, full CPython 3.12 x64, and MSVC C++17 with the Windows SDK.
- A local FM27 installation; the adapter reference build is `27.0.0+2493426`.
- A verified v1108.5 EXE from this repository's Releases, used to supply the matching initial inputs.

Install the save reader and its compression dependency from requirements.txt in the build environment.

## Prepare local inputs

Run these commands from the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/prepare_private.py --release-exe "D:\Downloads\FM27-Tactics-Lab-v1108.5.exe"
```

The script checks the original EXE and embedded payload SHA256, then reads only the named input assets into ignored `private/` directories. It does not execute the EXE. An existing matching asset directory can alternatively be supplied with `--assets-root` and `--catalog`.

## Build the native adapter

In an **x64 Native Tools Command Prompt for Visual Studio**:

```bat
.venv\Scripts\python.exe scripts\build_native.py --reference-dll "D:\Games\Football Manager 27\fm_Data\Plugins\x86_64\game_plugin.dll"
```

The public repository contains range metadata and digests. The script reconstructs comparison bytes from the exact reference DLL on your machine, verifies every range, then compiles the checked-in C++ host. Generated function bytes remain in ignored local outputs.

The build now runs `FM27Simulator.exe --check-image` against the exact
reference DLL immediately after linking; it stops on a blocked compatibility
contract. After compiling the two experimental fail-closed import stubs, it
runs `scripts/verify_platform_stub_exports.py` against the actual PE binaries.

The same build command compiles the two experimental fail-closed import stubs
from `native/platform_dependency_stub.cpp` into
`private/engine/fm27_native/platform-stubs/`. They supply the exact imported
PartyWin and PlayFab Multiplayer names; any unexpected call is logged and
terminates the worker instead of returning a fabricated result. Steam and EOS are loaded as fail-fast diagnostic probes in the current offline
runtime; their unexpected calls terminate the worker rather than fabricating a
successful platform response. The original game DLL is not modified. These
probes and PartyWin/PlayFab stubs are not a substitute for a real local-engine
match test; see [PLATFORM_DEPENDENCY_BOUNDARY.md](PLATFORM_DEPENDENCY_BOUNDARY.md).

## Native adapter registry

\`native/adapter_registry.json\` is the source of truth for distribution-specific
native adapters. Each enabled adapter has its own reference DLL identity,
profile metadata, version file, generated compatibility header and
\`FM27Simulator.exe\`. Shared runtime files and the fail-closed platform boundary
remain under \`private/engine/fm27_native\`.

The currently verified local reference is the Steam FM27 27.0.1 build
\`F79B0A34...\`. Build it with:

\`\`\`bat
.venv\Scripts\python.exe scripts\build_native.py --adapter steam_27_0_1_2494687 --reference-dll "D:\Games\Football Manager 27\fm_Data\Plugins\x86_64\game_plugin.dll"
\`\`\`

The runner selects an exact reference SHA256 automatically:

\`\`\`powershell
.venv\Scripts\python.exe scripts/run.py --game-root "D:\Games\Football Manager 27" --adapter auto
\`\`\`

An explicit \`--adapter ID\` is available for a deliberate compatibility trial.
When more than one adapter is enabled and a DLL hash matches none, selection is
required rather than silently treating an Epic build as Steam. The Epic slot is
currently reserved but disabled: it will only be enabled after the exact local
Epic DLL and its own validated ABI profile are available. Do not copy the
upstream Epic profile into this branch as a substitute for matching local
reference evidence.

## Run from source

```powershell
.venv\Scripts\python.exe scripts/run.py --game-root "D:\Games\Football Manager 27"
```

Open the printed loopback URL after startup. Press `Ctrl+C` to stop the source edition.

## Build a local desktop EXE

```powershell
.venv\Scripts\python.exe scripts/build_exe.py --python-home "D:\Python312"
```

Supply a full CPython 3.12 x64 distribution containing `Lib`, `DLLs`, `python312.dll`, the runtime libraries and `LICENSE.txt`. The script uses the .NET Framework C# compiler; `--csc` can override its location. Output: `dist/FM27-Tactics-Lab-v1108.5.exe`.

The build script packages the save reader from the active Python environment. The release EXE and a local build can have different hashes.

## Validate and export source

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts/export_source.py
```

The exporter uses an explicit source allowlist, checks for workstation paths and common credential formats, and writes file digests inside the archive. It excludes game DLLs, runtime data, input snapshots and generated comparison bytes.

The EXE release is a separate asset authorized for distribution by the maintainer. Its embedded initial inputs and comparison data are outside the MIT grant for tool code. See [third-party notices](../THIRD_PARTY_NOTICES.md).
