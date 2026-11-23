'use strict';
// Keep diagnostics outside the rerendered tactic workspace. No storage access.
function showEngineStatus(status){
 const e=status.engine_compatibility||status;
 document.querySelector('#engine-summary').textContent=e.can_simulate?(e.compatible?'本地引擎：关键接口检查通过':'本地引擎：尚未验证，可试运行'):'本地引擎：需要设置，战术编辑可正常使用';
 document.querySelector('#engine-message').textContent=e.message||'';
 document.querySelector('#engine-path').value=e.selected_game_root||'';
 document.querySelector('#engine-diagnostics').textContent=JSON.stringify({reason:e.reason,diagnostics:e.diagnostics,diagnostic_error:e.diagnostic_error,missing_files:e.missing_files},null,2);
 document.querySelector('#engine-details').open=!e.compatible;
 document.querySelector('#engine-smoke').disabled=!e.can_simulate;
}
window.addEventListener('DOMContentLoaded',async()=>{
 try{showEngineStatus(await api('/api/status'));}catch(e){document.querySelector('#engine-summary').textContent='引擎诊断读取失败：'+e.message;}
 document.querySelector('#engine-check').onclick=async()=>{
  const button=document.querySelector('#engine-check');button.disabled=true;
  try{showEngineStatus(await api('/api/engine/select',{path:document.querySelector('#engine-path').value}));}
  catch(e){document.querySelector('#engine-message').textContent=e.message;}
  finally{button.disabled=false;}
 };
 document.querySelector('#engine-smoke').onclick=async()=>{
  const button=document.querySelector('#engine-smoke'),output=document.querySelector('#engine-acceptance');
  button.disabled=true;button.textContent='正在运行原版比赛…';output.textContent='正在调用本机 FM27 原版比赛引擎。请保持程序运行，通常需要几十秒，最长约 190 秒。';
  try{
   const result=await api('/api/engine/smoke-match',{});
   output.textContent=JSON.stringify(result,null,2);
   if(result.ok){button.textContent='原版比赛验收通过';document.querySelector('#engine-summary').textContent='本地引擎：已完成一场原版比赛验收';}
   else{button.textContent='重新运行原版比赛验收';}
  }catch(e){output.textContent='验收请求失败：'+e.message;button.textContent='重新运行原版比赛验收';}
  finally{button.disabled=!((await api('/api/status').catch(()=>({engine_compatibility:{can_simulate:false}}))).engine_compatibility||{}).can_simulate;}
 };
});
