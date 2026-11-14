"""Resolve genuine FM27 runtime DLLs from known installation locations.

The resolver does not scan arbitrary directories or substitute SDK libraries.
Conflicting copies are rejected because Windows does not guarantee the order
of multiple AddDllDirectory user paths.
"""
import os
from pathlib import Path

RUNTIME_DLLS = (
    'icuuc65.dll',
    'icuin65.dll',
    'icudt65.dll',
    'EOSSDK-Win64-Shipping.dll',
    'PartyWin.dll',
    'PlayFabMultiplayerWin.dll',
    'steam_api64.dll',
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


def resolve_runtime_dlls(game_root=None, native_root=None):
    """Resolve required DLLs and report missing or conflicting copies."""
    directories = runtime_search_dirs(game_root, native_root)
    found = {}
    missing = []
    ambiguous = {}

    for name in RUNTIME_DLLS:
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

    return {
        'found': found,
        'missing': tuple(missing),
        'ambiguous': ambiguous,
        'search_dirs': directories,
    }
