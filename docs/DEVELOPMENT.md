# Building FM Tactics Lab v1112

This guide builds the source edition against a local FM27 game directory. The native profile is selected by the exact `game_plugin.dll` build identity; it is not a Steam/Epic storefront adapter.

## Requirements

- Windows x64, CPython 3.12 x64, and MSVC C++17 with the Windows SDK.
- A complete local FM27 27.0.1+2494687 game directory.
- A verified v1112 FM Tactics Lab release EXE if you need to extract the matching private tool inputs.

FM Tactics Lab does not start Steam or Epic clients and does not use a storefront registry to locate the game. Supply the game root directly or select it in the desktop launcher.

## Prepare local inputs

From the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/prepare_private.py --release-exe "D:\Downloads\FM27-Tactics-Lab-v1112.exe"
```

The preparation script verifies the release and extracts only the named initial tool assets into ignored `private/` directories. It does not execute the EXE.

## Build the local engine profile

In an **x64 Native Tools Command Prompt for Visual Studio**:

```bat
py -3.12 scripts\build_native.py --adapter local_27_0_1_2494687 --reference-dll "D:\Games\Football Manager 27\fm_Data\Plugins\x86_64\game_plugin.dll"
```

The public repository stores version-specific metadata and range digests, not copied game function bytes. The builder reconstructs the comparison profile from the exact local DLL, verifies the checksums and image layout, compiles the host, and runs `FM27Simulator.exe --check-image` before publishing the host.

The profile name identifies a local game binary/ABI build. It does not assert that Steam, Epic, or another client is installed or required.

## Run from source

In an ordinary CMD or PowerShell window:

```bat
py -3.12 scripts\run.py --game-root "D:\Games\Football Manager 27"
```

The source runner passes this path directly to the local engine host. Open the printed loopback URL after the service reports ready. Press `Ctrl+C` to stop it.

## Platform API boundary

The reference `game_plugin.dll` has static imports from Steamworks and Epic Online Services, in addition to PartyWin and PlayFab. The host does not launch either storefront client. Its current fail-closed API probes are diagnostic traps, not replacement implementations: an unexpected call is logged and terminates the worker. They never return successful authentication, ownership, entitlement, or online-service results.

This means the FMTL launcher itself is client-independent, but a successful no-client match still has to be demonstrated with the actual local engine build. A clean DLL load or `--check-image` result is not proof that a complete match can run without platform APIs. See [the platform API boundary report](PLATFORM_DEPENDENCY_BOUNDARY.md).

## Build a local desktop EXE

```powershell
py -3.12 scripts/build_exe.py --python-home "D:\Python312"
```

Supply a full CPython 3.12 x64 distribution and the .NET Framework C# compiler. The output is a local desktop build; the desktop launcher asks for a game directory instead of reading Steam installation metadata.

## Validate and export source

```powershell
py -3.12 -m unittest discover -s tests -v
py -3.12 scripts/export_source.py --output dist/FM27_Local_Engine_Source.zip
```

The exporter uses an explicit public-source allowlist, checks workstation paths and credentials, and excludes game DLLs, native binary payloads, private runtime assets, input snapshots, and generated comparison bytes.
