"""Resolve ICU runtime DLLs and the mandatory offline Steam/EOS boundary.
Normal match runs never search for genuine Steamworks/EOS runtimes. Their
imports always bind to local API-identifying fail-fast modules.
PartyWin and PlayFab use separate fail-fast stubs.
"""
import os
from pathlib import Path

RUNTIME_DLLS = ('icuuc65.dll', 'icuin65.dll', 'icudt65.dll')
FAIL_CLOSED_PLATFORM_STUBS = ('PartyWin.dll', 'PlayFabMultiplayerWin.dll')
PLATFORM_PROBE_DLLS = ('steam_api64.dll', 'EOSSDK-Win64-Shipping.dll')


def runtime_search_dirs(game_root=None, native_root=None):
    """Return deterministic locations for the genuine non-platform runtimes."""
    candidates = []
    if game_root is not None:
        game = Path(game_root)
        candidates.extend((
            game / 'fm_Data' / 'Plugins' / 'x86_64',
            game / 'fm_Data' / 'Plugins',
            game / 'fm_Data',
            game,
        ))
    if native_root is not None:
        native = Path(native_root)
        candidates.extend((native / 'libs', native))
    result = []
    seen = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve(strict=False)
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return tuple(result)


def resolve_runtime_dlls(game_root=None, native_root=None, platform_probe_mode=None):
    """Resolve ICU, Party/PlayFab stubs and mandatory offline Steam/EOS traps.

    platform_probe_mode remains accepted for old callers but is ignored:
    fail-closed platform isolation is now the only runtime mode.
    """
    directories = runtime_search_dirs(game_root, native_root)
    found, missing, ambiguous = {}, [], {}
    for name in RUNTIME_DLLS:
        matches = [directory / name for directory in directories
                   if (directory / name).is_file()]
        if not matches:
            missing.append(name)
        elif len(matches) == 1:
            found[name] = matches[0]
        else:
            first = matches[0]
            try:
                same_file = all(os.path.samefile(first, other) for other in matches[1:])
            except OSError:
                same_file = False
            if same_file:
                found[name] = first
            else:
                ambiguous[name] = tuple(matches)

    stubs, missing_stubs = {}, []
    if native_root is not None:
        stub_root = Path(native_root) / 'platform-stubs'
        for name in FAIL_CLOSED_PLATFORM_STUBS:
            path = stub_root / name
            if path.is_file():
                stubs[name] = path
            else:
                missing_stubs.append(name)
    else:
        missing_stubs.extend(FAIL_CLOSED_PLATFORM_STUBS)

    probes, missing_probes = {}, []
    if native_root is not None:
        probe_root = Path(native_root) / 'platform-probes'
        for name in PLATFORM_PROBE_DLLS:
            path = probe_root / name
            if path.is_file():
                probes[name] = path
            else:
                missing_probes.append(name)
    else:
        missing_probes.extend(PLATFORM_PROBE_DLLS)

    return {
        'found': found,
        'missing': tuple(missing),
        'ambiguous': ambiguous,
        'search_dirs': directories,
        'platform_stubs': stubs,
        'missing_platform_stubs': tuple(missing_stubs),
        'platform_probes': probes,
        'missing_platform_probes': tuple(missing_probes),
        'offline_platform_boundary': True,
        'platform_probe_mode': True,
    }
