"""Resolve FM27 native runtime dependencies and the selected platform API mode."""
import os
from pathlib import Path

RUNTIME_DLLS = ('icuuc65.dll', 'icuin65.dll', 'icudt65.dll')
FAIL_CLOSED_PLATFORM_STUBS = ('PartyWin.dll', 'PlayFabMultiplayerWin.dll')
PLATFORM_PROBE_DLLS = ('steam_api64.dll', 'EOSSDK-Win64-Shipping.dll')
PLATFORM_API_DLLS = PLATFORM_PROBE_DLLS
PLATFORM_API_MODES = ('diagnostic', 'genuine')


def runtime_search_dirs(game_root=None, native_root=None):
    """Return deterministic locations for ICU and diagnostic bundle assets."""
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


def _unique_file_matches(directories, name):
    matches = [directory / name for directory in directories
               if (directory / name).is_file()]
    if not matches:
        return None, ()
    first = matches[0]
    try:
        same_file = all(os.path.samefile(first, other) for other in matches[1:])
    except OSError:
        same_file = False
    if same_file:
        return first, ()
    return None, tuple(matches)


def resolve_runtime_dlls(game_root=None, native_root=None, platform_probe_mode=None,
                         platform_api_mode='diagnostic'):
    """Resolve ICU, Party/PlayFab traps, and genuine or diagnostic Steam/EOS APIs.

    The legacy platform_probe_mode parameter is accepted for compatibility but
    has no effect. Genuine mode loads the original SDK files found in the local
    game tree; diagnostic mode loads distinct fail-fast probes from the bundle.
    """
    mode = str(platform_api_mode or 'diagnostic').strip().lower()
    if mode not in PLATFORM_API_MODES:
        raise ValueError('platform_api_mode must be diagnostic or genuine')

    directories = runtime_search_dirs(game_root, native_root)
    found, missing, ambiguous = {}, [], {}
    for name in RUNTIME_DLLS:
        path, conflicts = _unique_file_matches(directories, name)
        if path is None and conflicts:
            ambiguous[name] = conflicts
        elif path is None:
            missing.append(name)
        else:
            found[name] = path

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
    api_modules, missing_api_modules, ambiguous_api_modules = {}, [], {}
    if mode == 'diagnostic':
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
    else:
        # Never fall back to bundled diagnostic modules in genuine mode.
        game_directories = runtime_search_dirs(game_root, None)
        for name in PLATFORM_API_DLLS:
            path, conflicts = _unique_file_matches(game_directories, name)
            if path is None and conflicts:
                ambiguous_api_modules[name] = conflicts
            elif path is None:
                missing_api_modules.append(name)
            else:
                api_modules[name] = path

    return {
        'found': found,
        'missing': tuple(missing),
        'ambiguous': ambiguous,
        'search_dirs': directories,
        'platform_stubs': stubs,
        'missing_platform_stubs': tuple(missing_stubs),
        'platform_probes': probes,
        'missing_platform_probes': tuple(missing_probes),
        'platform_api_modules': api_modules,
        'missing_platform_api_modules': tuple(missing_api_modules),
        'ambiguous_platform_api_modules': ambiguous_api_modules,
        'platform_api_mode': mode,
        'offline_platform_boundary': mode == 'diagnostic',
        'platform_probe_mode': mode == 'diagnostic',
    }
