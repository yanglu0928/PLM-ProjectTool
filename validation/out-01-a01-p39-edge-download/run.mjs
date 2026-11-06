import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { readFile, writeFile, mkdir, mkdtemp, rm, stat } from "node:fs/promises";
import { extname, join, resolve, sep, parse } from "node:path";
import { spawn } from "node:child_process";

const args=process.argv.slice(2);
function arg(name){const i=args.indexOf(name);return i<0?null:args[i+1]}
const dist=resolve(arg("--dist")||"");
const summaryPath=resolve(arg("--summary-out")||"");
const downloadDir=resolve(arg("--download-dir")||"");
const backendOrigin=arg("--backend-origin");
const liveConfigPath=arg("--live-config");
const liveConfig=liveConfigPath?JSON.parse(await readFile(resolve(liveConfigPath),"utf8")):null;
if(!arg("--dist")||!arg("--summary-out")||!arg("--download-dir"))throw new Error("dist, summary and download paths are required");
const runnerTemp=resolve(process.env.RUNNER_TEMP||"");
if(!runnerTemp||parse(runnerTemp).root.toLowerCase()!=="d:\\")throw new Error("GitHub hosted runner temp must be on D:");
if(!(await stat(join(dist,"index.html"))).isFile())throw new Error("frontend dist index.html missing");
await mkdir(downloadDir,{recursive:true});

const ids={
 project:"01234567-89ab-4cde-8123-456789abcdef",
 otherProject:"11234567-89ab-4cde-8123-456789abcdef",
 request:"21234567-89ab-4cde-8123-456789abcdef",
 badRequest:"31234567-89ab-4cde-8123-456789abcdef",
 failedRequest:"41234567-89ab-4cde-8123-456789abcdef",
 artifact:"51234567-89ab-4cde-8123-456789abcdef",
 document:"61234567-89ab-4cde-8123-456789abcdef",
 badDocument:"71234567-89ab-4cde-8123-456789abcdef",
 version:"81234567-89ab-4cde-8123-456789abcdef",
 badVersion:"91234567-89ab-4cde-8123-456789abcdef",
 actor:"a1234567-89ab-4cde-8123-456789abcdef",
 snapshot:"b1234567-89ab-4cde-8123-456789abcdef",
 template:"c1234567-89ab-4cde-8123-456789abcdef"
};
if(liveConfig?.ids)Object.assign(ids,liveConfig.ids);
const csrf="c".repeat(64), trace=ids.actor;
let payload=Buffer.from([0x50,0x4c,0x4d,0x20,0x73,0x79,0x6e,0x74,0x68,0x65,0x74,0x69,0x63,0x20,0x61,0x74,0x74,0x61,0x63,0x68,0x6d,0x65,0x6e,0x74,0x20,0x6f,0x6e,0x6c,0x79,0x0a,0x50,0x33,0x39,0x20,0x62,0x79,0x74,0x65,0x20,0x66,0x69,0x78,0x74,0x75,0x72,0x65,0x00,0x01,0x02,0xff]);
let digest=createHash("sha256").update(payload).digest("hex");
let mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document";
if(liveConfig){payload=Buffer.from(liveConfig.payload_hex,"hex");digest=createHash("sha256").update(payload).digest("hex");mime=liveConfig.mime;}
const reqs=[], now="2026-11-06T00:00:00Z";
function item(id,state,requestedAt){return {
 output_request_id:id,project_id:ids.project,output_type:"DOCX",template_version_ref:ids.template,
 source_version_refs:[ids.version],output_policy_ref:"output.policy.requirement-docx.v1",
 plugin_operation:"word.generate",context_snapshot_ref:ids.snapshot,context_fingerprint:"d".repeat(64),
 state,job_ref:ids.actor,execution_ref:null,generation_no:1,requested_at:requestedAt,
 completed_at:state==="SUCCEEDED"?now:null,etag:'"v1"'
}}
function envelope(data,status=200){return {status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"},body:JSON.stringify(status>=400?{error:{code:data},trace_id:trace}:{data,trace_id:trace})}}
async function proxyLiveBackend(req,res){
 const response=await fetch(backendOrigin+req.url,{method:req.method||"GET",headers:{
  cookie:req.headers.cookie||"",origin:"http://localhost:"+server.address().port
 }});
 const headers={};
 for(const [key,value] of response.headers){if(!["connection","transfer-encoding","keep-alive","content-encoding"].includes(key.toLowerCase()))headers[key]=value}
 res.writeHead(response.status,headers);res.end(Buffer.from(await response.arrayBuffer()));
}
const server=createServer(async(req,res)=>{
 const url=new URL(req.url||"/","http://localhost");
 const entry=url.pathname.startsWith("/api/")?{method:req.method||"GET",path:url.pathname,query:url.search,status:null}:null;
 if(entry){reqs.push(entry);res.on("finish",()=>entry.status=res.statusCode)}
 try{
  if(backendOrigin&&req.method==="GET"&&(/\/output-requests\/[^/]+\/artifact$/.test(url.pathname)||/\/documents\/[^/]+\/versions\/[^/]+\/content$/.test(url.pathname))){
   await proxyLiveBackend(req,res);return;
  }
  if(url.pathname==="/api/v1/auth/login"&&req.method==="POST"){
   let body="";for await(const chunk of req)body+=chunk;
   const value=JSON.parse(body);
   if(value.username!=="synthetic-user"||value.password!=="synthetic-only"){
    const out=envelope("AUTH_INVALID_CREDENTIALS",401);res.writeHead(out.status,out.headers);res.end(out.body);return;
   }
   const out=envelope({user:{user_id:ids.actor,username_display:"Synthetic hosted user"},
    deployment_role:"NONE",password_change_required:false,
    authorized_projects:[{project_id:ids.project,name:"Synthetic project",role:"PROJECT_MANAGER"}],
    absolute_expires_at:"2030-01-01T12:00:00Z",idle_expires_at:"2030-01-01T11:00:00Z",csrf_token:csrf});
   const cookies=["plm_synthetic_session=accepted; Path=/; HttpOnly; SameSite=Lax"];
   if(liveConfig)cookies.push("plm_session="+liveConfig.session_token_hex+"; Path=/; HttpOnly; SameSite=Lax");
   res.writeHead(out.status,{...out.headers,"Set-Cookie":cookies});
   res.end(out.body);return;
  }
  if(url.pathname==="/api/v1/projects/"+ids.project+"/output-requests"&&req.method==="GET"){
   const out=envelope({items:[
    item(ids.request,"SUCCEEDED","2026-11-06T00:03:00Z"),
    item(ids.badRequest,"SUCCEEDED","2026-11-06T00:02:00Z"),
    item(ids.failedRequest,"FAILED","2026-11-06T00:01:00Z")
   ],next_cursor:null,has_more:false});
   res.writeHead(out.status,out.headers);res.end(out.body);return;
  }
  if(url.pathname==="/api/v1/projects/"+ids.project+"/output-requests/"+ids.request+"/artifact"&&req.method==="GET"){
   const out=envelope({output_artifact_id:ids.artifact,output_request_id:ids.request,project_id:ids.project,
    document_id:ids.document,document_version_id:ids.version,artifact_kind:"DOCX",media_type:mime,
    content_sha256:digest,size_bytes:payload.length,
    content_url:"/api/v1/projects/"+ids.project+"/documents/"+ids.document+"/versions/"+ids.version+"/content"});
   res.writeHead(out.status,out.headers);res.end(out.body);return;
  }
  if(url.pathname==="/api/v1/projects/"+ids.project+"/output-requests/"+ids.badRequest+"/artifact"&&req.method==="GET"){
   const out=envelope({output_artifact_id:ids.artifact,output_request_id:ids.badRequest,project_id:ids.otherProject,
    document_id:ids.badDocument,document_version_id:ids.badVersion,artifact_kind:"DOCX",media_type:mime,
    content_sha256:digest,size_bytes:payload.length,
    content_url:"/api/v1/projects/"+ids.otherProject+"/documents/"+ids.badDocument+"/versions/"+ids.badVersion+"/content"});
   res.writeHead(out.status,out.headers);res.end(out.body);return;
  }
  if(url.pathname==="/api/v1/projects/"+ids.project+"/documents/"+ids.document+"/versions/"+ids.version+"/content"&&req.method==="GET"){
   res.writeHead(200,{"Content-Type":mime,"Content-Length":String(payload.length),
    "Content-Disposition":'attachment; filename="document-' + ids.version + '.bin"',
    "X-Content-Type-Options":"nosniff","Cache-Control":"no-store"});
   res.end(payload);return;
  }
  if(url.pathname.startsWith("/api/")){const out=envelope("RESOURCE_NOT_FOUND",404);res.writeHead(out.status,out.headers);res.end(out.body);return}
  let pathname=decodeURIComponent(url.pathname);if(pathname==="/"||pathname==="/login")pathname="/index.html";
  let file=resolve(dist,"."+pathname);if(file!==dist&&!file.startsWith(dist+sep))throw new Error("static path escape");
  try{if(!(await stat(file)).isFile())file=join(dist,"index.html")}catch{file=join(dist,"index.html")}
  const body=await readFile(file);
  const types={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".svg":"image/svg+xml",".png":"image/png",".woff2":"font/woff2",".json":"application/json"};
  res.writeHead(200,{"Content-Type":types[extname(file)]||"application/octet-stream","Cache-Control":"no-store"});res.end(body);
 }catch(error){res.writeHead(500,{"Content-Type":"text/plain"});res.end("synthetic hosted route failed: "+String(error))}
});
await new Promise((ok,bad)=>{server.once("error",bad);server.listen(0,"127.0.0.1",ok)});
const origin="http://localhost:"+server.address().port;
const profile=await mkdtemp(join(runnerTemp,"plm-out-p39-edge-profile-"));
const debugPort=12000+(process.pid%30000);
const edge=spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",[
 "--headless=new","--disable-background-networking","--disable-sync",
 "--remote-debugging-address=127.0.0.1","--remote-debugging-port="+debugPort,
 "--user-data-dir="+profile,"--no-first-run","--window-size=1450,1100",origin+"/login"
],{stdio:"ignore",windowsHide:true});
const pause=ms=>new Promise(resolvePause=>setTimeout(resolvePause,ms));
let socket,nextId=0,downloadWillBegin=null,downloadCompleted=false,clientProbe=null;
const pending=new Map(),checks=[],browserNetwork=[],networkFailures=[],runtimeExceptions=[];
async function getPage(){for(let i=0;i<300;i++){
 try{const entries=await(await fetch("http://127.0.0.1:"+debugPort+"/json/list")).json();
  const page=entries.find(x=>x.type==="page"&&x.url.startsWith(origin));if(page)return page
 }catch{}await pause(100)}
 throw new Error("Edge browser target did not appear");
}
function send(method,params={}){const id=++nextId;socket.send(JSON.stringify({id,method,params}));
 return new Promise((resolveSend,rejectSend)=>pending.set(id,{resolveSend,rejectSend}));
}
let harnessStage="startup",evaluationExceptionClass=null;
async function evaluate(expression){const out=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});
 if(out.exceptionDetails){evaluationExceptionClass=out.exceptionDetails.exception?.className||"unknown";throw new Error("CDP evaluation exception")};return out.result.value;
}
async function waitFor(expression,label){harnessStage=({"login form":"login-ready","synthetic login":"login-confirm","output history":"history-load","invalid cross-project reference":"cross-project-negative"})[label]||"wait";for(let i=0;i<300;i++){
 try{if(await evaluate("Boolean("+expression+")"))return}catch{}await pause(100)}
 throw new Error("timeout "+label);
}
async function click(label){harnessStage=label.includes("登录")?"login-submit":"button-click";const ok=await evaluate("(()=>{const e=[...document.querySelectorAll('button,a')].find(x=>x.textContent.trim()==="+JSON.stringify(label)+");if(!e)return false;e.click();return true})()");
 if(!ok)throw new Error("missing browser action: "+label);
}
async function setValue(selector,value){harnessStage="login-input";const ok=await evaluate("(()=>{const e=document.querySelector("+JSON.stringify(selector)+");if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,"+JSON.stringify(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 if(!ok)throw new Error("missing browser input: "+selector);
}
async function navigate(path){harnessStage="history-navigation";await evaluate("history.pushState({},'',"+JSON.stringify(path)+");dispatchEvent(new PopStateEvent('popstate'))")}
try{
 const page=await getPage();socket=new WebSocket(page.webSocketDebuggerUrl);
 await new Promise((ok,bad)=>{socket.addEventListener("open",ok,{once:true});socket.addEventListener("error",bad,{once:true})});
 socket.addEventListener("message",({data})=>{const msg=JSON.parse(data);
  if(msg.id&&pending.has(msg.id)){const p=pending.get(msg.id);pending.delete(msg.id);if(msg.error)p.rejectSend(new Error(msg.error.message));else p.resolveSend(msg.result);return}
  if(msg.method==="Network.requestWillBeSent"){const u=new URL(msg.params.request.url);if(u.pathname.startsWith("/api/"))browserNetwork.push({method:msg.params.request.method,path:u.pathname})}
  if(msg.method==="Network.loadingFailed")networkFailures.push({type:msg.params.type,error:msg.params.errorText});
  if(msg.method==="Runtime.exceptionThrown"){const e=msg.params.exceptionDetails||{};runtimeExceptions.push({class_name:e.exception?.className||"unknown",text:String(e.text||"").slice(0,160)})}
  if(msg.method==="Browser.downloadWillBegin")downloadWillBegin=msg.params;
  if(msg.method==="Browser.downloadProgress"&&msg.params.state==="completed")downloadCompleted=true;
 });
 await send("Runtime.enable");await send("Page.enable");await send("Network.enable");
 await send("Browser.setDownloadBehavior",{behavior:"allow",downloadPath:downloadDir,eventsEnabled:true});
 harnessStage="instrumentation";const instrumentation=await evaluate("(()=>{const nativeFetch=window.fetch;window.__p39NativeFetch=nativeFetch;window.__p39FetchTrace=[];window.__p39FetchRejects=[];const recordFetchReject=(url,method,error)=>{const category=error&&error.name==='AbortError'?'Abort':error&&error.name==='TypeError'?'TypeError':'Other';window.__p39FetchRejects.push({method,path:url.pathname,category})};window.fetch=function(...args){const input=args[0];const url=new URL(typeof input==='string'?input:input.url,location.href);const init=args[1]||{};const method=init.method||input.method||'GET';const api=url.pathname.startsWith('/api/');const signal=init.signal||input.signal||null;const credentials=['omit','same-origin','include'].includes(init.credentials)?init.credentials:'default';const cache=['default','no-store','reload','no-cache','force-cache','only-if-cached'].includes(init.cache)?init.cache:'other';const redirect=['follow','error','manual'].includes(init.redirect)?init.redirect:'default';const acceptJson=new Headers(init.headers||input.headers||undefined).get('Accept')==='application/json';if(api)window.__p39FetchTrace.push({method,path:url.pathname,origin_matches:url.origin===location.origin,signal_present:!!signal,signal_valid:!!signal&&signal instanceof AbortSignal,signal_aborted:!!signal?.aborted,credentials,cache,redirect,accept_json:acceptJson});try{const result=nativeFetch.apply(this,args);if(!api)return result;return Promise.resolve(result).catch(error=>{recordFetchReject(url,method,error);throw error})}catch(error){if(api)recordFetchReject(url,method,error);throw error}};const NativeAbort=window.AbortController;window.__p39AbortCount=0;window.AbortController=class extends NativeAbort{constructor(){super();window.__p39AbortCount++}};return {fetch_type:typeof window.fetch,abort_type:typeof NativeAbort}})()");
 assert.equal(instrumentation.fetch_type,"function");
 await waitFor("document.querySelector('#login-username')","login form");
 await setValue("#login-username","synthetic-user");await setValue("#login-password","synthetic-only");
 await click("登录 / 重新登录");await waitFor("document.body.innerText.includes('登录成功。')","synthetic login");
 await navigate("/projects/"+ids.project+"/output-requests");
 await waitFor("location.pathname==='/projects/"+ids.project+"/output-requests' && document.querySelectorAll('li').length===3","output history");
 harnessStage="history-ready";const clientBaseline=await evaluate("({fetch_calls:window.__p39FetchTrace.length,abort_count:window.__p39AbortCount,fetch_rejections:window.__p39FetchRejects.length})");
 harnessStage="failed-row-check";const failedHasDownload=await evaluate("(()=>{const li=[...document.querySelectorAll('li')].find(x=>x.innerText.includes("+JSON.stringify(ids.failedRequest)+"));return !!li&&[...li.querySelectorAll('button')].some(b=>b.innerText.trim()==='下载文件')})()");
 assert.equal(failedHasDownload,false,"FAILED output must not show download action");
 checks.push("FAILED output row exposes no download action");

 const validRefPath="/api/v1/projects/"+ids.project+"/output-requests/"+ids.request+"/artifact";
 const validContentPath="/api/v1/projects/"+ids.project+"/documents/"+ids.document+"/versions/"+ids.version+"/content";
 const clickSucceeded=async()=>{
  let probe=null;
  harnessStage="button-probe";for(let i=0;i<100;i++){
   probe=await evaluate("(()=>{const li=[...document.querySelectorAll('li')].find(x=>x.innerText.includes("+JSON.stringify(ids.request)+"));if(!li)return {found:false};const b=[...li.querySelectorAll('button')].find(x=>x.innerText.trim()==='下载文件');if(!b)return {found:false,row:li.innerText};b.scrollIntoView({block:'center'});const r=b.getBoundingClientRect();return {found:true,disabled:b.disabled,text:b.innerText.trim(),x:r.x+r.width/2,y:r.y+r.height/2,row:li.innerText}})()");
   if(probe&&probe.found&&!probe.disabled)break;
   await pause(100);
  }
  assert.ok(probe&&probe.found&&!probe.disabled,"download button was not ready: "+JSON.stringify(probe));
  harnessStage="artifact-mouse-click";await send("Input.dispatchMouseEvent",{type:"mouseMoved",x:probe.x,y:probe.y});
  await send("Input.dispatchMouseEvent",{type:"mousePressed",x:probe.x,y:probe.y,button:"left",clickCount:1});
  await send("Input.dispatchMouseEvent",{type:"mouseReleased",x:probe.x,y:probe.y,button:"left",clickCount:1});
  for(let i=0;i<100;i++){
   harnessStage="artifact-click-result";const alert=await evaluate("document.querySelector('[role=alert]')?.innerText||''");
   if(reqs.some(x=>x.path===validRefPath&&x.method==="GET"))return probe;
   if(alert){clientProbe=await evaluate("({fetch_calls:window.__p39FetchTrace,abort_count:window.__p39AbortCount,fetch_rejections:window.__p39FetchRejects})");const probeExpression="(async()=>{const run=async(mode)=>{const path="+JSON.stringify(validRefPath)+"+'?__p39_probe='+mode;const init={method:'GET',credentials:'same-origin',cache:'no-store',redirect:'error',headers:{Accept:'application/json'}};if(mode==='signal'){const controller=new AbortController();init.signal=controller.signal}try{const response=await window.__p39NativeFetch.call(window,path,init);return {probe:mode,outcome:'resolved',status:response.status,media_type:response.headers.get('content-type')?.split(';')[0]||null}}catch(error){const category=error&&error.name==='AbortError'?'Abort':error&&error.name==='TypeError'?'TypeError':'Other';return {probe:mode,outcome:'rejected',category}}};const controller=new AbortController();return {signal:{instance_valid:controller.signal instanceof AbortSignal,aborted:controller.signal.aborted},comparisons:[await run('bare'),await run('signal')]}})()";clientProbe.diagnostic_probe=await evaluate(probeExpression);throw new Error("download handler showed alert before reference request: "+JSON.stringify({probe,alert,clientBaseline,clientProbe,requests:reqs}))}
   await pause(50);
  }
  throw new Error("download click did not request Artifact reference: "+JSON.stringify({probe,diagnostics:await evaluate("({url:location.href,buttons:[...document.querySelectorAll('button')].map(b=>({text:b.innerText.trim(),disabled:b.disabled})),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.innerText)})"),requests:reqs}));
 };
 await clickSucceeded();
 for(let i=0;i<300&&!downloadCompleted;i++)await pause(100);
 assert.ok(downloadWillBegin,"Edge did not report attachment download; requests="+JSON.stringify(reqs));
 assert.ok(downloadCompleted,"Edge did not complete attachment download");
 const filename=downloadWillBegin.suggestedFilename;
 if(!backendOrigin)assert.equal(filename,"document-"+ids.version+".bin");
 else assert.ok(filename&&filename===filename.split(/[\\/]/).pop(),"live attachment filename escaped the download leaf");
 const downloadPath=join(downloadDir,filename);
 for(let i=0;i<100;i++){try{if((await stat(downloadPath)).isFile())break}catch{}await pause(50)}
 const saved=await readFile(downloadPath);
 assert.equal(saved.length,payload.length);
 assert.equal(createHash("sha256").update(saved).digest("hex"),digest);
 assert.deepEqual(saved,payload);
 assert.equal(reqs.filter(x=>x.path===validRefPath&&x.method==="GET").length,1);
 assert.equal(reqs.filter(x=>x.path===validContentPath&&x.method==="GET").length,1);
 checks.push("SUCCEEDED row resolves the same-origin Artifact reference and Edge saves exact attachment bytes/hash/length");

 harnessStage="cross-project-button-probe";const badProbe=await evaluate("(()=>{const li=[...document.querySelectorAll('li')].find(x=>x.innerText.includes("+JSON.stringify(ids.badRequest)+"));if(!li)return {found:false};const b=[...li.querySelectorAll('button')].find(x=>x.innerText.trim()==='下载文件');if(!b)return {found:false};b.scrollIntoView({block:'center'});const r=b.getBoundingClientRect();return {found:true,disabled:b.disabled,x:r.x+r.width/2,y:r.y+r.height/2}})()");
 assert.ok(badProbe&&badProbe.found&&!badProbe.disabled,"cross-project row download action was not ready: "+JSON.stringify(badProbe));
 harnessStage="cross-project-mouse-click";await send("Input.dispatchMouseEvent",{type:"mouseMoved",x:badProbe.x,y:badProbe.y});
 await send("Input.dispatchMouseEvent",{type:"mousePressed",x:badProbe.x,y:badProbe.y,button:"left",clickCount:1});
 await send("Input.dispatchMouseEvent",{type:"mouseReleased",x:badProbe.x,y:badProbe.y,button:"left",clickCount:1});
 await waitFor("document.querySelector('[role=alert]')?.innerText.includes('暂时无法获取输出文件')","invalid cross-project reference");
 const badContentPath="/api/v1/projects/"+ids.otherProject+"/documents/"+ids.badDocument+"/versions/"+ids.badVersion+"/content";
 assert.equal(reqs.filter(x=>x.path===badContentPath&&x.method==="GET").length,0);
 checks.push("cross-project reference fails before any content request or additional save");

 assert.ok(reqs.every(x=>x.path.startsWith("/api/v1/")),"observed API requests stayed on synthetic same-origin server");
 const summary={wbs:backendOrigin?"OUT-01-A01-P40":"OUT-01-A01-P39",status:"PASS_SCOPE_LIMITED",browser:"Microsoft Edge headless",
  backend_mode:backendOrigin?"live-fastapi-loopback":"synthetic-http-fixture",saved_file_matches_expected_bytes:true,
  cross_project_failed_closed:true,
  runner_os:"GitHub hosted Windows Server 2025",runner_drive:"D:",synthetic_data:true,controlled_api:true,
  checks,api_requests:reqs.map(x=>({method:x.method,path:x.path,status:x.status})),
  saved_bytes:saved.length,saved_sha256:digest,customer_data:false,external_api_calls:0,
  plugin_executed:false,formal_license_trust:false,backend_live:Boolean(backendOrigin),release_eligible:false};
 await writeFile(summaryPath,JSON.stringify(summary,null,2)+"\n","utf8");console.log(JSON.stringify(summary));
}catch(error){console.error(JSON.stringify({error:String(error),stage:harnessStage,evaluation_exception_class:evaluationExceptionClass,requests:reqs.slice(-30),browser_network:browserNetwork,network_failures:networkFailures,runtime_exceptions:runtimeExceptions,client_probe:clientProbe},null,2));process.exitCode=1}
finally{
 if(socket&&socket.readyState===WebSocket.OPEN)socket.close();
 edge.kill();await pause(300);
 await rm(profile,{recursive:true,force:true});await rm(downloadDir,{recursive:true,force:true});
 await new Promise(ok=>server.close(()=>ok()));
}