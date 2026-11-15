#define FM27_INPROCESS_DLL 1
#include "desktop_host.cpp"

#include <mutex>

static std::mutex fm27_inprocess_mutex;
static bool fm27_inprocess_poisoned=false;

static void fm27_inprocess_write(char* output,unsigned capacity,const char* value){
    if(!output||!capacity)return;
    output[0]=0;
    if(!value)return;
    strncpy_s(output,capacity,value,_TRUNCATE);
}
static bool fm27_inprocess_same_path(const fs::path& left,const fs::path& right){
    std::error_code error;
    auto a=fs::weakly_canonical(left,error);
    if(error)return false;
    error.clear();
    auto b=fs::weakly_canonical(right,error);
    if(error)return false;
    return _wcsicmp(a.c_str(),b.c_str())==0;
}
static bool fm27_inprocess_module_path(HMODULE module,fs::path& path){
    if(!module)return false;
    std::vector<wchar_t> buffer(32768);
    DWORD length=GetModuleFileNameW(module,buffer.data(),static_cast<DWORD>(buffer.size()));
    if(!length||length>=buffer.size())return false;
    path=fs::path(std::wstring(buffer.data(),length));
    return true;
}
static bool fm27_inprocess_module_contains(HMODULE module,const void* pointer){
    if(!module||!pointer)return false;
    auto base=reinterpret_cast<uintptr_t>(module);
    auto dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>0x100000)return false;
    auto nt=reinterpret_cast<const IMAGE_NT_HEADERS64*>(base+static_cast<uintptr_t>(dos->e_lfanew));
    if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC)return false;
    const auto address=reinterpret_cast<uintptr_t>(pointer);
    return address>=base&&address<base+nt->OptionalHeader.SizeOfImage;
}
static bool fm27_inprocess_ready(const wchar_t* requested_game_root,char* output,unsigned capacity){
    fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"invalid_request\"}");
    if(!requested_game_root||!*requested_game_root)return false;

    HMODULE fm=GetModuleHandleW(L"fm.exe");
    HMODULE unity=GetModuleHandleW(L"UnityPlayer.dll");
    HMODULE assembly=GetModuleHandleW(L"GameAssembly.dll");
    HMODULE plugin=GetModuleHandleW(L"game_plugin.dll");
    if(!fm||!unity||!assembly||!plugin){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"game_runtime_modules_missing\"}");
        return false;
    }

    fs::path game_root(requested_game_root),fm_path,plugin_path;
    if(!fm27_inprocess_module_path(fm,fm_path)||!fm27_inprocess_module_path(plugin,plugin_path)||
       !fm27_inprocess_same_path(fm_path.parent_path(),game_root)){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"game_root_process_mismatch\"}");
        return false;
    }
    const auto expected_plugin=game_root/L"fm_Data/Plugins/x86_64/game_plugin.dll";
    if(!fm27_inprocess_same_path(plugin_path,expected_plugin)){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"game_plugin_path_mismatch\"}");
        return false;
    }

    FILE* previous_log=log_file;
    FILE* sink=tmpfile();
    if(!sink){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"diagnostic_sink_unavailable\"}");
        return false;
    }
    log_file=sink;
    native_base=reinterpret_cast<unsigned char*>(plugin);
    const bool compatible=known_image(expected_plugin);
    fflush(sink);
    log_file=previous_log;
    fclose(sink);
    if(!compatible){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"registered_engine_profile_mismatch\"}");
        return false;
    }

    if(!compat_activation_flag){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"activation_gate_profile_missing\"}");
        return false;
    }
    const auto gate=*reinterpret_cast<volatile unsigned int*>(native_base+compat_activation_flag);
    if(gate!=0){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"game_initialization_pending\"}");
        return false;
    }

    const uintptr_t required_slots[]={
        0x0580EA08, // initialized table-A object
        0x0580ED90, // initialized table-B wrapper / thread context
        0x0580EC60, // startup context
        0x0580EB40, // resource manager
        0x0581CAB0, // game-owned callback interface
        0x0580E7B8  // thread context global
    };
    for(const auto rva:required_slots){
        if(!*reinterpret_cast<void**>(native_base+rva)){
            fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"game_startup_globals_incomplete\"}");
            return false;
        }
    }
    auto interface_object=*reinterpret_cast<void**>(native_base+0x0581CAB0);
    auto interface_vtable=*reinterpret_cast<void**>(interface_object);
    if(!fm27_inprocess_module_contains(plugin,interface_vtable)){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"game_interface_vtable_invalid\"}");
        return false;
    }

    // These modules must belong to the already-running, normally launched game.
    // This bridge never loads them, initializes them, or fabricates SDK results.
    if(!GetModuleHandleW(L"steam_api64.dll")||
       !GetModuleHandleW(L"steamclient64.dll")||
       !GetModuleHandleW(L"EOSSDK-Win64-Shipping.dll")){
        fm27_inprocess_write(output,capacity,"{\"ready\":false,\"reason\":\"authentic_platform_runtime_missing\"}");
        return false;
    }

    fm27_inprocess_write(output,capacity,
        "{\"ready\":true,\"runtime\":\"existing_fm27_process\",\"engine_profile\":\"verified\",\"activation_gate\":0,\"game_interface\":\"borrowed\",\"platform_sdk\":\"authentic_loaded\"}");
    return true;
}

extern "C" __declspec(dllexport) unsigned int __cdecl FM27InProcessAbiVersion(){
    return 1;
}

extern "C" __declspec(dllexport) int __cdecl FM27InProcessCheckReady(
    const wchar_t* game_root,char* response,unsigned int response_capacity){
    std::lock_guard<std::mutex> lock(fm27_inprocess_mutex);
    if(fm27_inprocess_poisoned){
        fm27_inprocess_write(response,response_capacity,"{\"ready\":false,\"reason\":\"worker_state_poisoned_restart_fm27\"}");
        return 91;
    }
    return fm27_inprocess_ready(game_root,response,response_capacity)?0:80;
}

extern "C" __declspec(dllexport) int __cdecl FM27InProcessCancel(){
    InterlockedExchange(&desktop_in_process_cancel_requested,1);
    return 0;
}

extern "C" __declspec(dllexport) int __cdecl FM27InProcessRunManifest(
    const wchar_t* game_root,const wchar_t* engine_root,const wchar_t* manifest_path,
    const wchar_t* session_log_path,char* response,unsigned int response_capacity){
    std::unique_lock<std::mutex> lock(fm27_inprocess_mutex,std::try_to_lock);
    if(!lock.owns_lock()){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"native_worker_busy\"}");
        return 92;
    }
    if(fm27_inprocess_poisoned){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"worker_state_poisoned_restart_fm27\"}");
        return 91;
    }
    if(!game_root||!*game_root||!engine_root||!*engine_root||
       !manifest_path||!*manifest_path||!session_log_path||!*session_log_path){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"invalid_request\"}");
        return 79;
    }
    char ready_response[1024]={};
    if(!fm27_inprocess_ready(game_root,ready_response,sizeof(ready_response))){
        fm27_inprocess_write(response,response_capacity,ready_response);
        return 80;
    }

    const fs::path game_path(game_root);
    const fs::path engine_path(engine_root);
    const fs::path native_path=engine_path/L"fm27_native";
    const fs::path manifest(fs::absolute(manifest_path));
    const fs::path session_path(fs::absolute(session_log_path));
    std::error_code error;
    if(!fs::is_regular_file(manifest,error)||error||
       !fs::is_regular_file(native_path/L"fixtures/match.pkm",error)||error){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"manifest_or_native_fixture_missing\"}");
        return 83;
    }
    error.clear();
    if(!fs::is_regular_file(native_path/L"FM27InProcessNative.dll",error)||error){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"inprocess_native_payload_missing\"}");
        return 84;
    }

    auto plugin=GetModuleHandleW(L"game_plugin.dll");
    if(!plugin){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"game_plugin_unloaded\"}");
        return 80;
    }
    native_base=reinterpret_cast<unsigned char*>(plugin);
    desktop_game_root=game_path;
    bundle=native_path;
    fixture=bundle/L"fixtures/match.pkm";
    output=session_path;
    worker_manifest=manifest;
    dump_input.clear();
    scenario_file.clear();
    seed_override=false;
    requested_seed=0;
    inspect_fixture_only=false;
    desktop_find_activation=false;
    policy_audit=false;
    tick_step=1;
    worker_bootstrapped=true; // Reuse the objects already initialized by the real FM process.
    desktop_use_genuine_platform_apis=true;
    desktop_in_process_mode=true;
    InterlockedExchange(&desktop_in_process_cancel_requested,0);

    log_file=_wfsopen(output.c_str(),L"w",_SH_DENYNO);
    if(!log_file){
        desktop_in_process_mode=false;
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"session_log_open_failed\"}");
        return 98;
    }

    int result=252;
    bool poisoned=false;
    FILE* session_log=log_file;
    try{
        fprintf(log_file,
            "{\"event\":\"inprocess_native_bridge_started\",\"pid\":%lu,\"game_root\":\"%ls\",\"game_owned_interface_borrowed\":true,\"one_time_bootstrap_reused\":true,\"platform_sdk_reinitialized\":false}\n",
            GetCurrentProcessId(),game_path.c_str());
        desktop_log_platform_module_state("inprocess_bridge_ready");
        fflush(log_file);
        auto interface_object=*reinterpret_cast<void**>(native_base+0x0581CAB0);
        result=worker_loop(interface_object);
        fprintf(log_file,"{\"event\":\"inprocess_native_worker_completed\",\"return_code\":%d}\n",result);
        fflush(log_file);
    }catch(const desktop_worker_abort& failure){
        poisoned=true;
        result=static_cast<int>(failure.code);
        if(log_file){
            fprintf(log_file,"{\"event\":\"inprocess_native_worker_aborted\",\"return_code\":%u,\"fm_process_terminated\":false}\n",failure.code);
            fflush(log_file);
        }
    }catch(const std::exception& failure){
        poisoned=true;
        result=253;
        if(log_file){
            fprintf(log_file,"{\"event\":\"inprocess_native_worker_exception\",\"fm_process_terminated\":false,\"message\":\"native_exception\"}\n");
            fflush(log_file);
        }
    }catch(...){
        poisoned=true;
        result=254;
        if(log_file){
            fputs("{\"event\":\"inprocess_native_worker_unknown_exception\",\"fm_process_terminated\":false}\n",log_file);
            fflush(log_file);
        }
    }

    // worker_loop owns per-match output files but not the session log. On an
    // abort, log_file may still point at the incomplete match file.
    if(log_file&&log_file!=session_log){
        fflush(log_file);
        fclose(log_file);
    }
    log_file=session_log;
    if(session_log){
        fflush(session_log);
        FlushFileBuffers(reinterpret_cast<HANDLE>(_get_osfhandle(_fileno(session_log))));
        fclose(session_log);
    }
    log_file=nullptr;
    desktop_in_process_mode=false;
    InterlockedExchange(&desktop_in_process_cancel_requested,0);
    fm27_inprocess_poisoned=poisoned;
    if(poisoned){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"native_worker_aborted_restart_fm27\",\"worker_state_poisoned\":true}");
    }else if(result!=0){
        fm27_inprocess_write(response,response_capacity,"{\"ok\":false,\"reason\":\"native_worker_returned_error\",\"worker_state_poisoned\":false}");
    }else{
        fm27_inprocess_write(response,response_capacity,"{\"ok\":true,\"worker_state_poisoned\":false,\"runtime\":\"existing_fm27_process\"}");
    }
    return result;
}
