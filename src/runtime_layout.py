"""Resolve genuine FM27 runtime DLLs and bundled fail-closed platform stubs.

Only the small set of known installation directories is searched. Steam and
EOS remain genuine runtime dependencies. PartyWin and PlayFab Multiplayer are
provided by build-generated stubs whose exports fail-fast if unexpectedly
called; they never synthesize successful platform or ownership responses.
"""
import os
from pathlib import Path

RUNTIME_DLLS = (
    'icuuc65.dll',
    'icuin65.dll',
    'icudt65.dll',
    'EOSSDK-Win64-Shipping.dll',
    'steam_api64.dll',
)

FAIL_CLOSED_PLATFORM_STUBS = (
    'PartyWin.dll',
    'PlayFabMultiplayerWin.dll',
)

PLATFORM_PROBE_DLLS = (
    'steam_api64.dll',
    'EOSSDK-Win64-Shipping.dll',
)


def runtime_search_dirs(game_root=None, native_root=None):
    """Return deterministic runtime search locations in priority order."""
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
    """Resolve engine DLLs, fail-closed stubs, and optional diagnostic probes."""
    if platform_probe_mode is None:
        platform_probe_mode = os.environ.get('FM27_PLATFORM_PROBE_MODE') == '1'
    directories = runtime_search_dirs(game_root, native_root)
    found = {}
    missing = []
    ambiguous = {}

    for name in RUNTIME_DLLS:
        if platform_probe_mode and name in PLATFORM_PROBE_DLLS:
            continue
        matches = [
            directory / name
            for directory in directories
            if (directory / name).is_file()
        ]
        if not matches:
            missing.append(name)
            continue
        if len(matches) == 1:
            found[name] = matches[0]
            continue

        first = matches[0]
        try:
            same_file = all(os.path.samefile(first, other) for other in matches[1:])
        except OSError:
            same_file = False
        if same_file:
            found[name] = first
        else:
            ambiguous[name] = tuple(matches)

    stubs = {}
    missing_stubs = []
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

    probes = {}
    missing_probes = []
    if platform_probe_mode:
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
        'platform_probe_mode': bool(platform_probe_mode),
    }
