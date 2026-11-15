using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;

namespace FMTL.NativeBridge;

[BepInPlugin(PluginId, PluginName, PluginVersion)]
public sealed class NativeBridgePlugin : BasePlugin
{
    public const string PluginId = "fm27.tacticslab.nativebridge";
    public const string PluginName = "FMTL Native Bridge";
    public const string PluginVersion = "0.1.0";

    private HttpListener? _listener;
    private CancellationTokenSource? _stop;
    private readonly SemaphoreSlim _nativeWorker = new(1, 1);
    private readonly ConcurrentDictionary<string, BridgeJob> _jobs = new();
    private ConfigEntry<int>? _port;
    private ConfigEntry<string>? _token;
    private ConfigEntry<bool>? _enabled;
    private string _gameRoot = "";

    public override void Load()
    {
        _port = Config.Bind("Bridge", "Port", 5122, "FMTL local bridge port.");
        _token = Config.Bind("Bridge", "Token", CreateToken(), "Local-only request token. Keep this secret.");
        _enabled = Config.Bind("NativeWorker", "Enabled", false,
            "Enable experimental native match execution inside this FM27 process. Keep disabled until deliberately testing.");
        Config.Save();

        var executable = Process.GetCurrentProcess().MainModule?.FileName;
        _gameRoot = string.IsNullOrWhiteSpace(executable) ? "" : Path.GetDirectoryName(executable) ?? "";
        if (string.IsNullOrWhiteSpace(_gameRoot))
        {
            Log.LogError("Could not resolve the FM27 process directory; bridge was not started.");
            return;
        }

        _listener = new HttpListener();
        _listener.Prefixes.Add($"http://localhost:{_port.Value}/");
        try
        {
            _listener.Start();
        }
        catch (Exception exception)
        {
            Log.LogError($"Could not start the localhost bridge: {exception.Message}");
            _listener.Close();
            _listener = null;
            return;
        }

        _stop = new CancellationTokenSource();
        _ = AcceptLoopAsync(_stop.Token);
        Log.LogInfo($"FMTL Native Bridge {PluginVersion} listening on localhost:{_port.Value}; native worker enabled={_enabled.Value}.");
        Log.LogInfo($"Bridge config: BepInEx/config/{PluginId}.cfg. Native worker is opt-in and defaults to disabled.");
    }

    public override bool Unload()
    {
        try
        {
            NativeBridge.Cancel();
        }
        catch
        {
        }
        _stop?.Cancel();
        _listener?.Close();
        // The native bridge module deliberately remains loaded until FM exits. It borrows
        // FM-owned objects and must not be unloaded while the game process is alive.
        return true;
    }

    private async Task AcceptLoopAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested && _listener is { IsListening: true })
        {
            HttpListenerContext context;
            try
            {
                context = await _listener.GetContextAsync();
            }
            catch (Exception) when (cancellationToken.IsCancellationRequested || _listener is not { IsListening: true })
            {
                return;
            }
            catch (Exception exception)
            {
                Log.LogWarning($"Bridge accept failed: {exception.Message}");
                await Task.Delay(200, cancellationToken).ContinueWith(_ => { });
                continue;
            }

            _ = HandleAsync(context, cancellationToken);
        }
    }

    private async Task HandleAsync(HttpListenerContext context, CancellationToken cancellationToken)
    {
        if (context.Request.RemoteEndPoint is not { Address: var address } || !IPAddress.IsLoopback(address))
        {
            await ReplyAsync(context, 403, new { ok = false, reason = "loopback_only" });
            return;
        }

        if (!string.Equals(context.Request.Headers["X-FMTL-Token"], _token?.Value, StringComparison.Ordinal))
        {
            await ReplyAsync(context, 401, new { ok = false, reason = "token_required" });
            return;
        }

        try
        {
            var path = context.Request.Url?.AbsolutePath ?? "/";
            if (path == "/health" && context.Request.HttpMethod == "GET")
            {
                await ReplyAsync(context, 200, new
                {
                    ok = true,
                    bridge = PluginVersion,
                    nativeWorkerEnabled = _enabled?.Value == true,
                    gameRoot = _gameRoot,
                    port = _port?.Value
                });
                return;
            }

            if (path == "/cancel" && context.Request.HttpMethod == "POST")
            {
                var cancelled = NativeBridge.Cancel();
                await ReplyAsync(context, 200, new { ok = true, cancelRequested = cancelled });
                return;
            }

            if (path == "/run" && context.Request.HttpMethod == "POST")
            {
                if (_enabled?.Value != true)
                {
                    await ReplyAsync(context, 403, new { ok = false, reason = "native_worker_disabled_in_config" });
                    return;
                }

                var request = await JsonSerializer.DeserializeAsync<RunRequest>(context.Request.InputStream,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true }, cancellationToken);
                if (request is null || string.IsNullOrWhiteSpace(request.EngineRoot) ||
                    string.IsNullOrWhiteSpace(request.Manifest) || string.IsNullOrWhiteSpace(request.SessionLog))
                {
                    await ReplyAsync(context, 400, new { ok = false, reason = "invalid_request" });
                    return;
                }

                if (!_nativeWorker.Wait(0))
                {
                    await ReplyAsync(context, 409, new { ok = false, reason = "native_worker_busy" });
                    return;
                }

                var id = Guid.NewGuid().ToString("N");
                var job = new BridgeJob(id);
                _jobs[id] = job;
                _ = Task.Run(() => RunJobAsync(job, request));
                await ReplyAsync(context, 202, new { ok = true, jobId = id, status = "running" });
                return;
            }

            if (path == "/status" && context.Request.HttpMethod == "GET")
            {
                var id = context.Request.QueryString["id"];
                if (string.IsNullOrWhiteSpace(id) || !_jobs.TryGetValue(id, out var job))
                {
                    await ReplyAsync(context, 404, new { ok = false, reason = "job_not_found" });
                    return;
                }

                await ReplyAsync(context, 200, new
                {
                    ok = true,
                    jobId = job.Id,
                    status = job.Status,
                    returnCode = job.ReturnCode,
                    result = job.Result,
                    startedUtc = job.StartedUtc,
                    completedUtc = job.CompletedUtc
                });
                return;
            }

            await ReplyAsync(context, 404, new { ok = false, reason = "unknown_endpoint" });
        }
        catch (OperationCanceledException)
        {
            await ReplyAsync(context, 503, new { ok = false, reason = "bridge_stopping" });
        }
        catch (Exception exception)
        {
            Log.LogError($"Bridge request failed: {exception}");
            await ReplyAsync(context, 500, new { ok = false, reason = "bridge_request_failed", message = exception.Message });
        }
    }

    private async Task RunJobAsync(BridgeJob job, RunRequest request)
    {
        job.Status = "running";
        job.StartedUtc = DateTimeOffset.UtcNow;
        try
        {
            var (code, result) = await Task.Run(() => NativeBridge.Run(_gameRoot, request.EngineRoot!, request.Manifest!, request.SessionLog!));
            job.ReturnCode = code;
            job.Result = result;
            job.Status = code == 0 ? "completed" : "failed";
        }
        catch (Exception exception)
        {
            job.ReturnCode = 255;
            job.Result = JsonSerializer.Serialize(new { ok = false, reason = "native_bridge_exception", message = exception.Message });
            job.Status = "failed";
            Log.LogError($"Native job {job.Id} failed: {exception}");
        }
        finally
        {
            job.CompletedUtc = DateTimeOffset.UtcNow;
            _nativeWorker.Release();
        }
    }

    private static string CreateToken()
    {
        var bytes = RandomNumberGenerator.GetBytes(32);
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static async Task ReplyAsync(HttpListenerContext context, int status, object value)
    {
        try
        {
            var bytes = JsonSerializer.SerializeToUtf8Bytes(value);
            context.Response.StatusCode = status;
            context.Response.ContentType = "application/json; charset=utf-8";
            context.Response.ContentLength64 = bytes.Length;
            await context.Response.OutputStream.WriteAsync(bytes);
            context.Response.Close();
        }
        catch
        {
            try { context.Response.Abort(); } catch { }
        }
    }

    private sealed class RunRequest
    {
        public string? EngineRoot { get; set; }
        public string? Manifest { get; set; }
        public string? SessionLog { get; set; }
    }

    private sealed class BridgeJob(string id)
    {
        public string Id { get; } = id;
        public volatile string Status = "queued";
        public int ReturnCode = -1;
        public string? Result;
        public DateTimeOffset StartedUtc;
        public DateTimeOffset? CompletedUtc;
    }
}

internal static class NativeBridge
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int AbiVersionDelegate();

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int CheckReadyDelegate(IntPtr gameRoot, IntPtr response, uint capacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int RunManifestDelegate(IntPtr gameRoot, IntPtr engineRoot, IntPtr manifest,
        IntPtr sessionLog, IntPtr response, uint capacity);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int CancelDelegate();

    private static readonly object LoadLock = new();
    private static IntPtr _library;
    private static string? _libraryPath;
    private static CheckReadyDelegate? _checkReady;
    private static RunManifestDelegate? _runManifest;
    private static CancelDelegate? _cancel;

    public static (int Code, string Result) Run(string gameRoot, string engineRoot, string manifest, string sessionLog)
    {
        var nativePath = Path.GetFullPath(Path.Combine(engineRoot, "fm27_native", "FM27InProcessNative.dll"));
        EnsureLoaded(nativePath);

        using var response = new NativeBuffer(16 * 1024);
        using var game = new NativeString(gameRoot);
        var ready = _checkReady!(game.Pointer, response.Pointer, (uint)response.Capacity);
        var readyText = response.ReadUtf8();
        if (ready != 0)
        {
            return (ready, string.IsNullOrWhiteSpace(readyText) ? "{\"ready\":false}" : readyText);
        }

        response.Clear();
        using var engine = new NativeString(Path.GetFullPath(engineRoot));
        using var manifestPath = new NativeString(Path.GetFullPath(manifest));
        using var logPath = new NativeString(Path.GetFullPath(sessionLog));
        var code = _runManifest!(game.Pointer, engine.Pointer, manifestPath.Pointer, logPath.Pointer,
            response.Pointer, (uint)response.Capacity);
        var result = response.ReadUtf8();
        return (code, string.IsNullOrWhiteSpace(result) ? "{\"ok\":false,\"reason\":\"empty_native_response\"}" : result);
    }

    public static bool Cancel()
    {
        lock (LoadLock)
        {
            return _cancel is not null && _cancel() == 0;
        }
    }

    private static void EnsureLoaded(string path)
    {
        lock (LoadLock)
        {
            if (_library != IntPtr.Zero)
            {
                if (!string.Equals(_libraryPath, path, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("A different native bridge DLL is already loaded. Restart FM27 before changing engine builds.");
                return;
            }

            if (!File.Exists(path))
                throw new FileNotFoundException("FMTL in-process native DLL was not found.", path);

            _library = NativeLibrary.Load(path);
            _libraryPath = path;
            var abi = Marshal.GetDelegateForFunctionPointer<AbiVersionDelegate>(
                NativeLibrary.GetExport(_library, "FM27InProcessAbiVersion"));
            if (abi() != 1)
                throw new InvalidOperationException("Unsupported FMTL in-process native ABI.");

            _checkReady = Marshal.GetDelegateForFunctionPointer<CheckReadyDelegate>(
                NativeLibrary.GetExport(_library, "FM27InProcessCheckReady"));
            _runManifest = Marshal.GetDelegateForFunctionPointer<RunManifestDelegate>(
                NativeLibrary.GetExport(_library, "FM27InProcessRunManifest"));
            _cancel = Marshal.GetDelegateForFunctionPointer<CancelDelegate>(
                NativeLibrary.GetExport(_library, "FM27InProcessCancel"));
        }
    }

    private sealed class NativeString : IDisposable
    {
        public NativeString(string value) => Pointer = Marshal.StringToHGlobalUni(value);
        public IntPtr Pointer { get; private set; }
        public void Dispose()
        {
            if (Pointer == IntPtr.Zero) return;
            Marshal.FreeHGlobal(Pointer);
            Pointer = IntPtr.Zero;
        }
    }

    private sealed class NativeBuffer : IDisposable
    {
        public NativeBuffer(int capacity)
        {
            Capacity = capacity;
            Pointer = Marshal.AllocHGlobal(capacity);
            Clear();
        }
        public int Capacity { get; }
        public IntPtr Pointer { get; private set; }
        public void Clear()
        {
            for (var i = 0; i < Capacity; i++) Marshal.WriteByte(Pointer, i, 0);
        }
        public string ReadUtf8() => Marshal.PtrToStringUTF8(Pointer) ?? "";
        public void Dispose()
        {
            if (Pointer == IntPtr.Zero) return;
            Marshal.FreeHGlobal(Pointer);
            Pointer = IntPtr.Zero;
        }
    }
}
