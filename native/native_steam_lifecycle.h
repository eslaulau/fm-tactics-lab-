// This process never creates a genuine Steamworks session.
// Steam/EOS APIs are bound to local fail-fast modules, not a live platform SDK.
#pragma once
static HANDLE desktop_cancel_event=nullptr;
static std::wstring desktop_cancel_name;
// In-process mode is owned by the bridge DLL inside the already-running FM process.
// It must never shut down Steam, unload the game module, or terminate the host process.
struct desktop_worker_abort { unsigned code; };
static bool desktop_in_process_mode=false;
static volatile LONG desktop_in_process_cancel_requested=0;

static bool desktop_steam_cleanup(){
    if(log_file){
        fputs("{\"event\":\"offline_platform_cleanup_skipped\",\"reason\":\"fail_closed_offline_boundary\",\"real_steam_session\":false}\n",log_file);
        fflush(log_file);
    }
    return true;
}
[[noreturn]] static void desktop_finish_and_exit(unsigned code){
    if(desktop_in_process_mode)throw desktop_worker_abort{code};
    if(!desktop_steam_cleanup()&&!code)code=180;
    if(desktop_cancel_event){CloseHandle(desktop_cancel_event);desktop_cancel_event=nullptr;}
    if(log_file){fflush(log_file);FlushFileBuffers((HANDLE)_get_osfhandle(_fileno(log_file)));}
    if(log_file){fputs("{\"event\":\"host_orderly_exit_requested\",\"stack_unwound\":false,\"dll_detach_enabled\":true}\n",log_file);fflush(log_file);}
    ExitProcess(code);
    for(;;)Sleep(INFINITE);
}
static void desktop_check_cancel(){
    if(InterlockedCompareExchange(&desktop_in_process_cancel_requested,0,0)!=0){
        if(log_file){fputs("{\"event\":\"native_match_cancelled\",\"full_match_completed\":false}\n",log_file);fflush(log_file);}
        desktop_finish_and_exit(86);
    }
    if(desktop_cancel_event&&WaitForSingleObject(desktop_cancel_event,0)==WAIT_OBJECT_0){
        if(log_file){fputs("{\"event\":\"native_match_cancelled\",\"full_match_completed\":false}\n",log_file);fflush(log_file);}
        desktop_finish_and_exit(86);
    }
}
