using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyVersion("1.112.0.0")]
[assembly: AssemblyFileVersion("1.112.0.0")]
[assembly: AssemblyInformationalVersion("v1112")]

internal static class Program {
    static string L(string zh,string en){return System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName=="zh"?zh:en;}
    static Process server;
    static StreamWriter output,error;
    static string dataRoot,url,gameRoot;
    static string GetArg(string[] args,string key,string fallback=null){for(int i=0;i+1<args.Length;i++)if(args[i]==key)return args[i+1];return fallback;}
    static bool Has(string[] args,string key){return Array.IndexOf(args,key)>=0;}
    static string Quote(string value){return "\""+value.Replace("\"", "\\\"")+"\"";}
    static bool IsEngine(string path){return !String.IsNullOrEmpty(path)&&File.Exists(Path.Combine(path,"fm27_native","FM27Simulator.exe"))&&File.Exists(Path.Combine(path,"fm27_native","editor_manual_default.json"));}
    static string EngineRoot(string[] args,string release){
        string configured=Path.Combine(dataRoot,"engine-root.txt");
        string[] candidates={GetArg(args,"--engine-root"),Environment.GetEnvironmentVariable("FM27_ENGINE_ROOT"),Path.Combine(release,"engine"),File.Exists(configured)?File.ReadAllText(configured).Trim():null,Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..",".."))};
        foreach(string p in candidates)if(IsEngine(p))return Path.GetFullPath(p);
        if(Has(args,"--self-test"))throw new Exception(L("找不到完整的本机引擎环境。","Cannot find the complete local engine environment."));
        using(var dialog=new FolderBrowserDialog()){dialog.Description=L("请选择已有的 FmEngine 工具目录（包含 fm27_native 文件夹），不是游戏安装目录。","Select the FmEngine tool folder containing fm27_native.");if(dialog.ShowDialog()!=DialogResult.OK||!IsEngine(dialog.SelectedPath))throw new Exception(L("未选择有效的引擎工具目录。","No valid engine tool folder selected."));return dialog.SelectedPath;}
    }
    static string FindGame(string[] args){
        string saved=Path.Combine(dataRoot,"game-root.txt");
        string[] candidates={GetArg(args,"--game-root"),Environment.GetEnvironmentVariable("FM27_GAME_ROOT"),File.Exists(saved)?File.ReadAllText(saved).Trim():null};
        foreach(string path in candidates){
            if(String.IsNullOrWhiteSpace(path))continue;
            string full;
            try{full=Path.GetFullPath(path.Trim());}
            catch(ArgumentException){continue;}
            catch(NotSupportedException){continue;}
            if(Directory.Exists(full)){File.WriteAllText(saved,full,Encoding.UTF8);return full;}
        }
        if(Has(args,"--self-test")||Has(args,"--test-lifecycle"))return "";
        using(var dialog=new FolderBrowserDialog()){
            dialog.Description=L("选择本地 FM27 游戏根目录（包含 fm_Data 和 shared）。工具不会启动 Steam 或 Epic。","Select the local FM27 game root containing fm_Data and shared. The tool does not launch Steam or Epic.");
            if(dialog.ShowDialog()==DialogResult.OK){
                string selected=Path.GetFullPath(dialog.SelectedPath);
                if(!Directory.Exists(Path.Combine(selected,"fm_Data"))||!Directory.Exists(Path.Combine(selected,"shared")))
                    throw new Exception(L("所选目录不是完整的 FM27 游戏根目录。","The selected folder is not a complete FM27 game root."));
                File.WriteAllText(saved,selected,Encoding.UTF8);
                return selected;
            }
        }
        return "";
    }
    static string Unpack(){
        byte[] payload;using(Stream source=Assembly.GetExecutingAssembly().GetManifestResourceStream("DesktopPayload"))using(var memory=new MemoryStream()){source.CopyTo(memory);payload=memory.ToArray();}
        string hash;using(var sha=SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(payload)).Replace("-","").Substring(0,20).ToLowerInvariant();
        string root=Path.Combine(dataRoot,"releases",hash),ready=Path.Combine(root,".ready");if(File.Exists(ready))return root;
        Directory.CreateDirectory(root);string prefix=Path.GetFullPath(root)+Path.DirectorySeparatorChar;
        using(var memory=new MemoryStream(payload))using(var archive=new ZipArchive(memory,ZipArchiveMode.Read))foreach(var entry in archive.Entries){
            string dest=Path.GetFullPath(Path.Combine(root,entry.FullName));if(!dest.StartsWith(prefix,StringComparison.OrdinalIgnoreCase))throw new Exception(L("安装包包含非法路径。","The package contains an invalid path."));
            if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(dest);continue;}Directory.CreateDirectory(Path.GetDirectoryName(dest));using(var source=entry.Open())using(var target=File.Create(dest))source.CopyTo(target);
        }
        File.WriteAllText(ready,hash);return root;
    }
    static string ReadUrl(string address){var request=(HttpWebRequest)WebRequest.Create(address);request.Timeout=1200;request.Proxy=null;using(var response=request.GetResponse())using(var reader=new StreamReader(response.GetResponseStream(),Encoding.UTF8))return reader.ReadToEnd();}
    static int ChoosePort(int requested){try{var listener=new TcpListener(IPAddress.Loopback,requested);listener.Start();int port=((IPEndPoint)listener.LocalEndpoint).Port;listener.Stop();return port;}catch(SocketException){var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();int port=((IPEndPoint)listener.LocalEndpoint).Port;listener.Stop();return port;}}
    static void StartServer(string release,string engine,int port,string adapter){
        Directory.CreateDirectory(Path.Combine(dataRoot,"logs"));string stamp=DateTime.Now.ToString("yyyyMMdd_HHmmss_fff");output=new StreamWriter(Path.Combine(dataRoot,"logs",stamp+".stdout.log"),false,Encoding.UTF8);error=new StreamWriter(Path.Combine(dataRoot,"logs",stamp+".stderr.log"),false,Encoding.UTF8);output.AutoFlush=error.AutoFlush=true;
        var info=new ProcessStartInfo(Path.Combine(release,"python","python.exe"),Quote(Path.Combine(release,"source","desktop_server.py"))+" --port "+port){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=engine,RedirectStandardOutput=true,RedirectStandardError=true};
        info.EnvironmentVariables["FM27_ENGINE_ROOT"]=engine;info.EnvironmentVariables["FM27_DESKTOP_DATA"]=dataRoot;info.EnvironmentVariables["PYTHONUTF8"]="1";info.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"]="1";
        foreach(System.Collections.DictionaryEntry item in Environment.GetEnvironmentVariables())if(((string)item.Key).StartsWith("FM27_")&&(string)item.Key!="FM27_ENGINE_ROOT"&&(string)item.Key!="FM27_DESKTOP_DATA")info.EnvironmentVariables.Remove((string)item.Key);
        info.EnvironmentVariables["FM27_GAME_ROOT"]=gameRoot;
        if(!String.IsNullOrWhiteSpace(adapter))info.EnvironmentVariables["FM27_ENGINE_ADAPTER"]=adapter;
        info.EnvironmentVariables["FM27_UI_LANGUAGE"]=System.Globalization.CultureInfo.CurrentUICulture.Name;
        server=new Process{StartInfo=info};server.OutputDataReceived+=(s,e)=>{if(e.Data!=null)lock(output)output.WriteLine(e.Data);};server.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)lock(error)error.WriteLine(e.Data);};server.Start();server.BeginOutputReadLine();server.BeginErrorReadLine();url="http://127.0.0.1:"+port;
        for(int i=0;i<160;i++){if(server.HasExited)throw new Exception(L("后台启动失败。请查看日志：","Server failed to start. See logs: ")+Path.Combine(dataRoot,"logs"));try{if(ReadUrl(url+"/api/status").Contains("original_native")){File.WriteAllText(Path.Combine(dataRoot,"url.txt"),url);return;}}catch(WebException){}Thread.Sleep(125);}
        throw new Exception(L("后台启动超时。请查看日志：","Server startup timed out. See logs: ")+Path.Combine(dataRoot,"logs"));
    }
    static void OpenApp(){
        string[] browsers={Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),@"Microsoft\Edge\Application\msedge.exe"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),@"Microsoft\Edge\Application\msedge.exe"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),@"Google\Chrome\Application\chrome.exe")};
        foreach(string browser in browsers)if(File.Exists(browser)){Process.Start(new ProcessStartInfo(browser,"--app="+url+" --window-size=1540,1000 --user-data-dir="+Quote(Path.Combine(dataRoot,"browser"))){UseShellExecute=false});return;}
        Process.Start(new ProcessStartInfo(url){UseShellExecute=true});
    }
    static void Stop(){if(server!=null){try{if(!server.HasExited){server.Kill();server.WaitForExit(5000);}server.WaitForExit();}catch(InvalidOperationException){}server.Dispose();}if(output!=null)output.Dispose();if(error!=null)error.Dispose();}
    [STAThread]static int Main(string[] args){
        dataRoot=Path.GetFullPath(GetArg(args,"--data-dir",Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"FM27TacticsDesktop")));Directory.CreateDirectory(dataRoot);
        bool selfTest=Has(args,"--self-test"),lifecycleTest=Has(args,"--test-lifecycle");string testIdentity="";if(selfTest||lifecycleTest)using(var sha=SHA256.Create())testIdentity="_SelfTest_"+BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(dataRoot.ToLowerInvariant()))).Replace("-","").Substring(0,16);bool acquired;using(var mutex=new Mutex(true,"Local\\FM27TacticsDesktop_Editor"+testIdentity,out acquired)){
            if(!acquired){if(File.Exists(Path.Combine(dataRoot,"url.txt"))){url=File.ReadAllText(Path.Combine(dataRoot,"url.txt"));OpenApp();}return 0;}
            try{
                string release=Unpack();string engine=EngineRoot(args,release);gameRoot=FindGame(args);File.WriteAllText(Path.Combine(dataRoot,"engine-root.txt"),engine,Encoding.UTF8);StartServer(release,engine,ChoosePort(Int32.Parse(GetArg(args,"--port","18765"))),GetArg(args,"--adapter"));
                if(selfTest){foreach(string path in new[]{"/api/catalog","/api/defaults","/api/phase-defaults","/desktop.js","/desktop.css","/engine-settings.js","/save-mode.js","/squad-editor.js","/tactic-pool.js","/tactic-library.js","/api/locale","/i18n.js","/i18n-en.js"})if(ReadUrl(url+path).Length<10)throw new Exception("Empty endpoint: "+path);File.WriteAllText(Path.Combine(dataRoot,"self-test.json"),"{\"ok\":true,\"bundled_python\":true,\"native_match_executed\":false,\"url\":\""+url+"\"}");Stop();return 0;}
                Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
                using(var appIcon=Icon.ExtractAssociatedIcon(Application.ExecutablePath))using(var context=new ApplicationContext())using(var tray=new NotifyIcon())using(var menu=new ContextMenuStrip())using(var timer=new System.Windows.Forms.Timer()){
                    tray.Text=L("FM 战术实验室 · v1112","FM Tactics Lab \u00b7 v1112");tray.Icon=appIcon??SystemIcons.Application;tray.ContextMenuStrip=menu;tray.Visible=!lifecycleTest;
                    menu.Items.Add(L("打开战术板","Open tactics board"),null,(s,e)=>OpenApp());menu.Items.Add(L("打开结果目录","Open results folder"),null,(s,e)=>Process.Start(new ProcessStartInfo(dataRoot){UseShellExecute=true}));menu.Items.Add(L("退出","Exit"),null,(s,e)=>context.ExitThread());tray.DoubleClick+=(s,e)=>OpenApp();
                    DateTime launched=DateTime.UtcNow;bool seenPage=false;int failedChecks=0;
                    timer.Interval=2000;timer.Tick+=(s,e)=>{
                        if(server.HasExited){timer.Stop();context.ExitThread();return;}
                        try{string presence=ReadUrl(url+"/api/desktop-presence");failedChecks=0;seenPage=seenPage||presence.Contains("\"seen\": true");if(presence.Contains("\"close_ready\": true")||(!seenPage&&!Has(args,"--no-browser")&&(DateTime.UtcNow-launched).TotalSeconds>120)){timer.Stop();context.ExitThread();}}
                        catch(WebException){if(++failedChecks>=10){timer.Stop();context.ExitThread();}}
                    };
                    timer.Start();if(!Has(args,"--no-browser"))OpenApp();try{Application.Run(context);}finally{timer.Stop();tray.Visible=false;Stop();}return 0;
                }
            }catch(Exception ex){Stop();File.WriteAllText(Path.Combine(dataRoot,"startup-error.txt"),ex.ToString(),Encoding.UTF8);if(!selfTest)MessageBox.Show(ex.Message,L("FM 战术实验室 · v1112","FM Tactics Lab \u00b7 v1112"),MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}
        }
    }
}
