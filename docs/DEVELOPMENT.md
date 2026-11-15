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

## Experimental in-process FM27 bridge

The default `isolated` mode remains unchanged. An optional `inprocess` mode is being developed for builds that cannot initialize `game_plugin.dll` in a fresh child process.

This mode requires the original FM27 executable to be started normally from its supported storefront, with the user's valid game session. It does not start or emulate a storefront, does not initialize Steam/EOS on the game's behalf, does not change the game's activation gate, and does not patch the original `game_plugin.dll`.

### Build

1. Install BepInEx 6 for Unity IL2CPP into the FM27 game directory and start FM27 normally once so the loader is initialized.
2. In an x64 Native Tools Command Prompt for Visual Studio, build the adapter as usual:

```bat
py -3.12 scripts\build_native.py --adapter local_27_0_1_2494687 --reference-dll "D:\Games\Football Manager 27\fm_Data\Plugins\x86_64\game_plugin.dll"
```

The build now produces an adapter-specific `FM27InProcessNative.dll` beside its matching `FM27Simulator.exe`. Do not copy a bridge DLL from another game build or adapter.

3. Build and deploy the BepInEx bridge plugin while FM27 is closed:

```powershell
dotnet build integration\BepInEx\FMTL.NativeBridge\FMTL.NativeBridge.csproj -p:FM27Dir="D:\Games\Football Manager 27"
```

4. Start FM27 normally again. The plugin creates `BepInEx\config\fm27.tacticslab.nativebridge.cfg`. Review the local token and change `[NativeWorker] Enabled = false` to `true` only when deliberately testing this experimental mode. Restart FM27 after changing the setting.

### Run

With FM27 running normally and the bridge enabled, use:

```powershell
py -3.12 scripts\run.py --game-root "D:\Games\Football Manager 27" --platform-api-mode genuine --execution-mode inprocess
```

The bridge only accepts loopback HTTP requests carrying its BepInEx-generated token. It checks that the selected game root matches the running `fm.exe`, that the original game modules and genuine platform SDK modules are present, that the registered native image profile matches, and that the game's activation gate and startup globals are already initialized. It borrows the game's existing interface object; it does not create or release that object.

**Limitations and safety:** this is an experimental native integration, not a validated release feature. It forces one worker at a time because the game process owns shared native globals. A native error or cancellation can leave the in-process worker state unusable; the bridge then refuses more jobs and requires a full FM27 restart. A severe native fault may still terminate FM27. Back up saves, keep FM idle, and do not use this mode while a career match is in progress. Successful compilation does not establish that a full match can complete; accept a result only after the native end-of-match, statistics, per-match release, and TLS-restoration receipts all pass.

The plugin defaults to disabled, and the original isolated mode remains the default unless `--execution-mode inprocess` is explicitly supplied.

## Platform API boundary

The reference `game_plugin.dll` has static imports from Steamworks and Epic Online Services, in addition to PartyWin and PlayFab. The FMTL launcher does not start either storefront client. The default `diagnostic` mode binds Steam/EOS imports to fail-fast probes. The optional `genuine` mode instead loads the original `steam_api64.dll` and `EOSSDK-Win64-Shipping.dll` from the selected game directory and verifies every expected IAT slot resolves to those exact modules.

Run the genuine-SDK mode with:

```powershell
py -3.12 scripts/run.py --game-root "D:\Games\Football Manager 27" --platform-api-mode genuine
```

This mode does not call Steam/EOS initialization functions itself, does not start a storefront client, and does not fabricate authentication, ownership, entitlement, or online-service results. The original engine may call the authentic SDKs during its own initialization; their real result is preserved. An SDK or anti-tamper component may still require the supported platform launch context or account authorization. This mode is a diagnostic comparison, not a way to bypass those requirements. A clean DLL load or `--check-image` result is not proof that a complete match can run. See [the platform API boundary report](PLATFORM_DEPENDENCY_BOUNDARY.md).

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
