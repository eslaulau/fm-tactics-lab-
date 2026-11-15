'use strict';
// Keep diagnostics outside the rerendered tactic workspace. No storage access.
let isolatedWorkerCount = null;
function syncExecutionModeControls(mode){
 const workers=document.querySelector('#workers');
 if(!workers)return;
 if(mode==='inprocess'){
  if(!workers.disabled)isolatedWorkerCount=workers.value;
  workers.value='1';workers.disabled=true;workers.title='FM27 进程内模式只支持单路串行';
 }else{
  workers.disabled=false;workers.removeAttribute('title');
  if(isolatedWorkerCount!==null){workers.value=isolatedWorkerCount;isolatedWorkerCount=null;}
 }
}
function showEngineStatus(status){
 const e=status.engine_compatibility||status;
 const mode=e.native_execution_mode||'isolated';
 syncExecutionModeControls(mode);
 document.querySelector('#engine-summary').textContent=e.can_simulate?(mode==='inprocess'?'本地引擎：FM27 进程内实验模式已就绪':e.compatible?'本地引擎：关键接口检查通过':'本地引擎：尚未验证，可试运行'):'本地引擎：需要设置，战术编辑可正常使用';
 document.querySelector('#engine-message').textContent=e.message||'';
 document.querySelector('#engine-path').value=e.selected_game_root||'';
 document.querySelector('#engine-mode').value=mode;
 document.querySelector('#engine-mode-help').textContent=mode==='inprocess'
  ?'当前为实验模式：必须由 Steam 正常启动 FM27，并加载 BepInEx Native Bridge；插件配置 NativeWorker Enabled 必须为 true。比赛强制单路串行，不会关闭 FM 的 Steam 会话。原生异常或取消超时可能需要完整重启 FM27。'
  :'当前为独立宿主模式（默认）。FMTL 会尝试在单独的原生进程中运行比赛；不会改变 FM27 进程。';
 document.querySelector('#engine-diagnostics').textContent=JSON.stringify({reason:e.reason,diagnostics:e.diagnostics,diagnostic_error:e.diagnostic_error,missing_files:e.missing_files,inprocess_bridge:e.inprocess_bridge},null,2);
 document.querySelector('#engine-details').open=!e.compatible||mode==='inprocess';
}
window.addEventListener('DOMContentLoaded',async()=>{
 try{showEngineStatus(await api('/api/status'));}catch(e){document.querySelector('#engine-summary').textContent='引擎诊断读取失败：'+e.message;}
 document.querySelector('#engine-check').onclick=async()=>{
  const button=document.querySelector('#engine-check');button.disabled=true;
  try{showEngineStatus(await api('/api/engine/select',{path:document.querySelector('#engine-path').value}));}
  catch(e){document.querySelector('#engine-message').textContent=e.message;}
  finally{button.disabled=false;}
 };
 document.querySelector('#engine-mode-apply').onclick=async()=>{
  const button=document.querySelector('#engine-mode-apply');
  const selector=document.querySelector('#engine-mode');
  const selected=selector.value;
  button.disabled=true;
  try{
   const status=await api('/api/engine/mode',{mode:selected});
   showEngineStatus(status);
   document.querySelector('#engine-message').textContent=status.execution_mode_persistence_warning||'比赛执行方式已切换。';
  }catch(e){
   document.querySelector('#engine-message').textContent=e.message;
   try{showEngineStatus(await api('/api/status'));}catch(_){}
   if(selected==='inprocess'){
    document.querySelector('#engine-details').open=true;
    document.querySelector('#engine-mode-help').textContent='进程内模式未启用。请先正常启动 FM27、安装 BepInEx 插件并将 NativeWorker Enabled 设为 true，再重新检查。';
   }
  }finally{button.disabled=false;}
 };
});
