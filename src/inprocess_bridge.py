"""Local client for the opt-in BepInEx bridge inside the running FM27 process."""
import io
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


PLUGIN_ID = "fm27.tacticslab.nativebridge"
DEFAULT_PORT = 5122
POLL_INTERVAL = 0.25


def _read_bridge_config(game_root):
    path = Path(game_root) / "BepInEx" / "config" / (PLUGIN_ID + ".cfg")
    if not path.is_file():
        raise RuntimeError(
            "FMTL Native Bridge 未安装或尚未启动：找不到 " + str(path)
        )
    section = ""
    values = {}
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[(section.lower(), key.strip().lower())] = value.strip()
    token = values.get(("bridge", "token"), "")
    port_text = values.get(("bridge", "port"), str(DEFAULT_PORT))
    try:
        port = int(port_text)
    except ValueError as error:
        raise RuntimeError("BepInEx Native Bridge 配置中的端口无效") from error
    if not token or len(token) < 32:
        raise RuntimeError("BepInEx Native Bridge 缺少有效的本机请求令牌")
    if not 1024 <= port <= 65535:
        raise RuntimeError("BepInEx Native Bridge 端口超出有效范围")
    return port, token


class _BridgeClient:
    def __init__(self, game_root):
        self.game_root = Path(game_root).resolve()
        self.port, self.token = _read_bridge_config(self.game_root)
        self.base_url = f"http://127.0.0.1:{self.port}"

    def request(self, path, method="GET", body=None, timeout=5):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"X-FMTL-Token": self.token}
        if data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"FMTL Native Bridge HTTP {error.code}: {detail[:600]}"
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError(
                "无法连接 FM27 进程内桥接服务。请确认 FM27 已正常启动并加载 "
                "BepInEx 插件；" + str(error)
            ) from error

    def health(self):
        status = self.request("/health")
        if not status.get("ok"):
            raise RuntimeError("FMTL Native Bridge 健康检查失败")
        if not status.get("nativeWorkerEnabled"):
            raise RuntimeError(
                "进程内比赛执行尚未启用。检查 "
                "BepInEx/config/fm27.tacticslab.nativebridge.cfg，"
                "将 [NativeWorker] Enabled 设置为 true 后重启 FM27。"
            )
        if not status.get("gameRoot") or Path(status["gameRoot"]).resolve() != self.game_root:
            raise RuntimeError("FMTL Native Bridge 连接到的不是所选 FM27 游戏目录")
        return status


def bridge_health(game_root):
    """Check that the in-game BepInEx plugin is active and native execution is opted in."""
    return _BridgeClient(game_root).health()


class InProcessCancellation:
    """Cancellation handle compatible with the standalone MatchCancellation interface."""
    def __init__(self, game_root):
        self.client = _BridgeClient(game_root)

    def signal(self):
        self.client.request("/cancel", method="POST", body={}, timeout=5)

    def close(self):
        pass


class InProcessBridgeProcess:
    """Subprocess-like polling wrapper around an asynchronous in-game native worker job."""
    def __init__(self, game_root, engine_root, manifest, session_log):
        self.client = _BridgeClient(game_root)
        self.client.health()
        self.returncode = None
        self.stdout = io.BytesIO()
        self._last_poll = 0.0
        self._output = b""
        self._status = None
        response = self.client.request(
            "/run",
            method="POST",
            body={
                "engineRoot": str(Path(engine_root).resolve()),
                "manifest": str(Path(manifest).resolve()),
                "sessionLog": str(Path(session_log).resolve()),
            },
            timeout=10,
        )
        self.job_id = response.get("jobId")
        if not response.get("ok") or not self.job_id:
            raise RuntimeError("FM27 Native Bridge 未能接收批次任务：" + json.dumps(response, ensure_ascii=False))

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        now = time.monotonic()
        if now - self._last_poll < POLL_INTERVAL:
            return None
        self._last_poll = now
        query = urllib.parse.urlencode({"id": self.job_id})
        status = self.client.request("/status?" + query, timeout=5)
        self._status = status
        if status.get("status") in ("completed", "failed"):
            self.returncode = int(status.get("returnCode", 255))
            result = status.get("result")
            if isinstance(result, str):
                self._output = result.encode("utf-8", errors="replace")
            else:
                self._output = json.dumps(status, ensure_ascii=False).encode("utf-8")
            self.stdout = io.BytesIO(self._output)
        return self.returncode

    def wait(self, timeout=None):
        began = time.monotonic()
        while self.poll() is None:
            if timeout is not None and time.monotonic() - began >= timeout:
                raise subprocess.TimeoutExpired("FM27 in-process native worker", timeout)
            time.sleep(0.05)
        return self.returncode

    def communicate(self, input=None, timeout=None):
        self.wait(timeout)
        return self._output, None

    def kill(self):
        if self.returncode is None:
            try:
                self.client.request("/cancel", method="POST", body={}, timeout=5)
            except Exception:
                pass

    terminate = kill
