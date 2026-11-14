"""Resolve the local FM27 build to one registered native adapter and stage its host."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess

try:
    from .runtime_layout import resolve_runtime_dlls
except ImportError:
    from runtime_layout import resolve_runtime_dlls

LEASES = []


def close_leases():
    for stream in LEASES:
        stream.close()
    LEASES.clear()


def require_available(status):
    if not status.get('can_simulate'):
        raise ValueError('暂不能模拟：' + status.get('message', '请设置游戏目录并检查诊断'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_adapter_registry(native):
    """Load the runtime copy of the source adapter registry, if present."""
    path = Path(native) / 'adapter_registry.json'
    if not path.is_file():
        return None
    registry = json.loads(path.read_text(encoding='utf8'))
    if registry.get('schema_version') != 1 or not isinstance(registry.get('adapters'), list):
        raise ValueError('原生适配器注册表版本不受支持')
    ids = [item.get('id') for item in registry['adapters']]
    if not all(isinstance(value, str) and value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError('原生适配器注册表包含重复或无效 ID')
    if registry.get('default_adapter') not in ids:
        raise ValueError('原生适配器注册表没有有效的默认适配器')
    return registry


def select_adapter(registry, dll_sha256, requested=None):
    """Prefer an exact DLL identity; permit a deliberate profile trial fallback."""
    active = [item for item in registry['adapters'] if item.get('enabled') is True]
    by_id = {item['id']: item for item in registry['adapters']}
    if requested and requested != 'auto':
        spec = by_id.get(requested)
        if spec is None:
            raise ValueError(f'未知的引擎适配器：{requested}')
        if spec.get('enabled') is not True:
            reason = spec.get('reason') or '该发行版尚无验证配置'
            raise ValueError(f'适配器 {requested} 尚未准备好：{reason}')
        return spec, 'explicit'
    exact = [item for item in active
             if str(item.get('reference_sha256', '')).lower() == dll_sha256.lower()]
    if len(exact) == 1:
        return exact[0], 'exact_sha256'
    if len(exact) > 1:
        raise ValueError('多个适配器声明了相同 DLL 指纹，拒绝不确定选择')
    if len(active) == 1:
        return active[0], 'single_adapter_compatibility_candidate'
    if not active:
        raise ValueError('没有已启用的原生引擎适配器')
    raise ValueError(
        '本机 game_plugin.dll 未匹配已登记的构建。多适配器环境下请通过 FM27_ENGINE_ADAPTER 明确选择；'
        '不要把 Epic DLL 自动套用 Steam 的地址配置。'
    )


def _adapter_paths(native, spec):
    output = Path(spec['output_directory'])
    if output.is_absolute() or '..' in output.parts:
        raise ValueError(f'适配器 {spec["id"]} 的输出目录不安全')
    adapter_root = Path(native) / output
    executable = adapter_root / 'FM27Simulator.exe'
    profile = adapter_root / 'engine_compat_profile.json'
    version = adapter_root / 'adapter_version.json'
    return adapter_root, executable, profile, version


def _stage_legacy_entrypoints(native, executable, profile, version):
    """Keep old FMTL worker call sites on the selected adapter without rewriting them."""
    destinations = (
        (executable, Path(native) / 'FM27Simulator.exe'),
        (profile, Path(native) / 'engine_compat_profile.json'),
        (version, Path(native) / 'adapter_version.json'),
    )
    for source, target in destinations:
        if source is None or not Path(source).is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if Path(source).resolve() != target.resolve():
            shutil.copy2(source, target)


def lease(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        stream = open(msvcrt.open_osfhandle(handle, 0), 'rb')
    except BaseException:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        raise
    LEASES.append(stream)


def initialize(root):
    close_leases()
    os.environ.pop('FM27_EXPECTED_DLL_SHA256', None)
    native = Path(root) / 'fm27_native'
    game_root = Path(os.environ['FM27_GAME_ROOT']) if os.environ.get('FM27_GAME_ROOT') else None
    game = game_root if game_root is not None else native
    plugins = game / 'fm_Data/Plugins/x86_64' if game_root is not None else native / 'libs'
    dll = plugins / 'game_plugin.dll' if game_root is not None else native / 'game_plugin.dll'
    runtime = resolve_runtime_dlls(game_root, native)
    files = {
        'game_plugin.dll': dll,
        'icudt65l.dat': game / 'icudt65l.dat',
        'shared/data/simatch.fmf': game / 'shared/data/simatch.fmf',
        'shared/data/simatchshared.fmf': game / 'shared/data/simatchshared.fmf'
    }
    for name, path in runtime['found'].items():
        files['libs/' + name] = path
    for name, path in runtime['platform_stubs'].items():
        files['platform-stubs/' + name] = path
    for name, path in runtime['platform_probes'].items():
        files['platform-probes/' + name] = path
    runtime_dirs = [str(path) for path in runtime['search_dirs']]
    runtime_paths = {name: str(path) for name, path in sorted(runtime['found'].items())}
    status = {
        'policy': 'graded-adapter-compatibility-v2',
        'compatible': False,
        'can_simulate': False,
        'disposition': 'blocked',
        'selected_game_root': str(game.resolve()),
        'actual_dll_sha256': None,
        'resource_fingerprint': None,
        'runtime_search_dirs': runtime_dirs,
        'runtime_dlls': runtime_paths,
        'platform_stubs': {name: str(path) for name, path in sorted(runtime['platform_stubs'].items())},
        'platform_probe_mode': True,
        'offline_platform_boundary': True,
        'platform_probes': {name: str(path) for name, path in sorted(runtime['platform_probes'].items())},
        'whole_file_sha_is_admission_gate': False,
        'whole_engine_behavior_equivalence_proven': False
    }
    try:
        missing = [name for name, path in files.items() if not path.is_file()]
        missing.extend('libs/' + name for name in runtime['missing'])
        missing.extend('platform-stubs/' + name for name in runtime['missing_platform_stubs'])
        missing.extend('platform-probes/' + name for name in runtime['missing_platform_probes'])
        if missing:
            return {**status, 'reason': 'missing_resources', 'missing_files': missing,
                    'message': '请选择完整的游戏安装目录；缺少：' + ', '.join(missing)}
        if runtime['ambiguous']:
            ambiguous = {name: [str(path) for path in paths]
                         for name, paths in sorted(runtime['ambiguous'].items())}
            names = ', '.join(sorted(ambiguous))
            return {**status, 'reason': 'ambiguous_runtime_dlls', 'ambiguous_runtime_dlls': ambiguous,
                    'message': '多个目录存在不同版本的同名运行库，拒绝不确定加载：' + names}

        for path in files.values():
            lease(path)
        actual = sha(dll)
        registry = load_adapter_registry(native)
        requested = os.environ.get('FM27_ENGINE_ADAPTER', '').strip()
        if registry is None:
            if requested and requested != 'auto':
                close_leases()
                return {**status, 'reason': 'adapter_registry_missing',
                        'message': '当前引擎目录没有适配器注册表，请先重新构建原生适配器。'}
            spec = None
            adapter_selection = 'legacy_single_adapter'
            executable = native / 'FM27Simulator.exe'
            profile_path = native / 'engine_compat_profile.json'
            version_path = native / 'adapter_version.json'
        else:
            spec, adapter_selection = select_adapter(registry, actual, requested)
            _, executable, profile_path, version_path = _adapter_paths(native, spec)
            # Backward-compatible staging lets the existing batch worker,
            # provenance and diagnostics keep using fm27_native/FM27Simulator.exe.
            if not executable.is_file() or not profile_path.is_file() or not version_path.is_file():
                if spec['id'] == registry['default_adapter']:
                    executable = native / 'FM27Simulator.exe'
                    profile_path = native / 'engine_compat_profile.json'
                    version_path = native / 'adapter_version.json'
            if not executable.is_file() or not profile_path.is_file() or not version_path.is_file():
                close_leases()
                return {
                    **status,
                    'reason': 'adapter_build_missing',
                    'adapter_id': spec['id'],
                    'message': f'适配器 {spec["id"]} 尚未构建。请使用 scripts\\build_native.py --adapter {spec["id"]} 重新构建。'
                }
        if spec is not None:
            selected_profile = json.loads(profile_path.read_text(encoding='utf8'))
            selected_version = json.loads(version_path.read_text(encoding='utf8'))
            expected_reference = str(spec['reference_sha256']).lower()
            if (selected_profile.get('reference_sha256', '').lower() != expected_reference or
                    selected_version.get('reference_dll_sha256', '').lower() != expected_reference):
                close_leases()
                return {
                    **status,
                    'reason': 'adapter_metadata_mismatch',
                    'adapter_id': spec['id'],
                    'message': '适配器注册表、兼容配置和版本信息的 DLL 指纹不一致，已拒绝启动。'
                }

        status.update(
            actual_dll_sha256=actual,
            adapter_id=spec['id'] if spec else 'legacy',
            adapter_distribution=spec.get('distribution') if spec else 'legacy',
            adapter_selection=adapter_selection,
            adapter_reference_sha256=spec.get('reference_sha256') if spec else None,
            native_host_path=str(executable.resolve())
        )

        env = os.environ.copy()
        env.pop('FM27_EXPECTED_DLL_SHA256', None)
        diagnostic_error = None
        exit_code = None
        try:
            checked = subprocess.run(
                [str(executable), '--check-image', str(dll)],
                env=env, capture_output=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            exit_code = checked.returncode
            rows = []
            for line in checked.stdout.decode('utf8', errors='replace').splitlines():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
            diagnostic_error = checked.stderr.decode('utf8', errors='replace')[:2000]
        except (OSError, subprocess.TimeoutExpired) as error:
            rows = []
            diagnostic_error = str(error)
        validation = next((row for row in rows if row.get('event') == 'native_engine_compatibility'), None)
        if validation and not (validation.get('compatible') or validation.get('trial_allowed')):
            close_leases()
            return {
                **status, 'reason': validation.get('reason'), 'diagnostics': rows,
                'message': '关键接口或布局不匹配：' + str(validation.get('reason')) +
                           '，位置 ' + hex(validation.get('rva', 0))
            }
        if exit_code != 0 or not validation:
            close_leases()
            return {
                **status, 'reason': 'preflight_failed', 'diagnostics': rows,
                'diagnostic_error': diagnostic_error,
                'preflight_exit_code': exit_code,
                'message': '引擎未通过原生检查，请查看诊断信息。'
            }

        profile = json.loads(profile_path.read_text(encoding='utf8'))
        entries = [
            {'path': name, 'sha256': actual if name == 'game_plugin.dll' else sha(path)}
            for name, path in sorted(files.items())
        ]
        fingerprint = hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest()
        _stage_legacy_entrypoints(native, executable, profile_path, version_path)
        os.environ['FM27_EXPECTED_DLL_SHA256'] = actual
        verified = bool(validation.get('compatible'))
        status.update(
            profile=validation.get('profile'),
            compatible=verified,
            can_simulate=True,
            trial_allowed=not verified,
            disposition='verified' if verified else 'unverified',
            reason=validation.get('reason'),
            message='引擎关键接口检查通过' if verified else
                    '此版本尚未验证，可试运行；每场仍须通过原生完赛、比分和统计校验。',
            diagnostics=rows,
            diagnostic_error=diagnostic_error,
            resource_fingerprint=fingerprint,
            reference_dll_sha256=profile['reference_sha256'],
            original_build_verified=actual == profile['reference_sha256'],
            files=entries,
            whole_engine_behavior_equivalence_proven=False
        )
        return status
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        close_leases()
        return {
            **status,
            'reason': 'adapter_or_resource_access_failed',
            'message': '无法读取游戏资源或选择适配器：' + str(error)
        }
