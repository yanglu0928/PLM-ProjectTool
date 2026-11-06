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
const csrf="c".repeat(64), trace=ids.actor;
const payload=Buffer.from("PLM hosted synthetic attachment only\\nP39 browser download byte fixture\\x00\\x01\\x02\\xff","utf8");
const digest=createHash("sha256").update(payload).digest("hex");
const mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const reqs=[], now="2026-11-06T00:00:00Z";
function item(id,state,requestedAt){return {
 output_request_id:id,project_id:ids.project,output_type:"DOCX",template_version_ref:ids.template,
 source_version_refs:[ids.version],output_policy_ref:"output.policy.requirement-docx.v1",
 plugin_operation:"word.generate",context_snapshot_ref:ids.snapshot,context_fingerprint:"d".repeat(64),
 state,job_ref:ids.actor,execution_ref:null,generation_no:1,requested_at:requestedAt,
 completed_at:state==="SUCCEEDED"?now:null,etag:"\\"v1\\""
}}
function envelope(data,status=200){return {status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"},body:JSON.stringify(status>=400?{error:{code:data},trace_id:trace}:{data,trace_id:trace})}}
const server=createServer(async(req,res)=>{
 const url=new URL(req.url||"/","http://localhost");
 const entry={method:req.method||"GET",path:url.pathname,query:url.search,status:null};
 reqs.push(entry);res.on("finish",()=>entry.status=res.statusCode);
 try{
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
   res.writeHead(out.status,{...out.headers,"Set-Cookie":"plm_synthetic_session=accepted; Path=/; HttpOnly; SameSite=Lax"});
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
    "Content-Disposition":"attachment; filename=\\"document-"+ids.version+".bin\\"",
    "X-Content-Type-Options":"nosniff","Cache-Control":"no-store"});
   res.end(payload);return;
  }
  const out=envelope("RESOURCE_NOT_FOUND",404);res.writeHead(out.status,out.headers);res.end(out.body);
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
let socket,nextId=0,downloadWillBegin=null,downloadCompleted=false;
const pending=new Map(),checks=[];
async function getPage(){for(let i=0;i<300;i++){
 try{const entries=await(await fetch("http://127.0.0.1:"+debugPort+"/json/list")).json();
  const page=entries.find(x=>x.type==="page"&&x.url.startsWith(origin));if(page)return page
 }catch{}await pause(100)}
 throw new Error("Edge browser target did not appear");
}
function send(method,params={}){const id=++nextId;socket.send(JSON.stringify({id,method,params}));
 return new Promise((resolveSend,rejectSend)=>pending.set(id,{resolveSend,rejectSend}));
}
async function evaluate(expression){const out=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});
 if(out.exceptionDetails)throw new Error(out.exceptionDetails.text);return out.result.value;
}
async function waitFor(expression,label){for(let i=0;i<300;i++){
 try{if(await evaluate("Boolean("+expression+")"))return}catch{}await pause(100)}
 throw new Error("timeout "+label);
}
async function click(label){const ok=await evaluate("(()=>{const e=[...document.querySelectorAll('button,a')].find(x=>x.textContent.trim()==="+JSON.stringify(label)+");if(!e)return false;e.click();return true})()");
 if(!ok)throw new Error("missing browser action: "+label);
}
async function setValue(selector,value){const ok=await evaluate("(()=>{const e=document.querySelector("+JSON.stringify(selector)+");if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,"+JSON.stringify(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 if(!ok)throw new Error("missing browser input: "+selector);
}
async function navigate(path){await evaluate("history.pushState({},'',"+JSON.stringify(path)+");dispatchEvent(new PopStateEvent('popstate'))")}
try{
 const page=await getPage();socket=new WebSocket(page.webSocketDebuggerUrl);
 await new Promise((ok,bad)=>{socket.addEventListener("open",ok,{once:true});socket.addEventListener("error",bad,{once:true})});
 socket.addEventListener("message",({data})=>{const msg=JSON.parse(data);
  if(msg.id&&pending.has(msg.id)){const p=pending.get(msg.id);pending.delete(msg.id);if(msg.error)p.rejectSend(new Error(msg.error.message));else p.resolveSend(msg.result);return}
  if(msg.method==="Browser.downloadWillBegin")downloadWillBegin=msg.params;
  if(msg.method==="Browser.downloadProgress"&&msg.params.state==="completed")downloadCompleted=true;
 });
 await send("Runtime.enable");await send("Page.enable");
 await send("Browser.setDownloadBehavior",{behavior:"allow",downloadPath:downloadDir,eventsEnabled:true});
 await waitFor("document.querySelector('#login-username')","login form");
 await setValue("#login-username","synthetic-user");await setValue("#login-password","synthetic-only");
 await click("登录 / 重新登录");await waitFor("document.body.innerText.includes('登录成功。')","synthetic login");
 await navigate("/projects/"+ids.project+"/output-requests");
 await waitFor("location.pathname==='/projects/"+ids.project+"/output-requests' && document.querySelectorAll('li').length===3","output history");
 const failedHasDownload=await evaluate("(()=>{const li=[...document.querySelectorAll('li')].find(x=>x.innerText.includes("+JSON.stringify(ids.failedRequest)+"));return !!li&&[...li.querySelectorAll('button')].some(b=>b.innerText.trim()==='下载文件')})()");
 assert.equal(failedHasDownload,false,"FAILED output must not show download action");
 checks.push("FAILED output row exposes no download action");

 const validRefPath="/api/v1/projects/"+ids.project+"/output-requests/"+ids.request+"/artifact";
 const validContentPath="/api/v1/projects/"+ids.project+"/documents/"+ids.document+"/versions/"+ids.version+"/content";
 await evaluate("(()=>{const li=[...document.querySelectorAll('li')].find(x=>x.innerText.includes("+JSON.stringify(ids.request)+"));const b=[...li.querySelectorAll('button')].find(x=>x.innerText.trim()==='下载文件');b.click();return true})()");
 for(let i=0;i<300&&!downloadCompleted;i++)await pause(100);
 assert.ok(downloadWillBegin,"Edge did not report attachment download");
 assert.ok(downloadCompleted,"Edge did not complete attachment download");
 const filename=downloadWillBegin.suggestedFilename;
 assert.equal(filename,"document-"+ids.version+".bin");
 const downloadPath=join(downloadDir,filename);
 for(let i=0;i<100;i++){try{if((await stat(downloadPath)).isFile())break}catch{}await pause(50)}
 const saved=await readFile(downloadPath);
 assert.equal(saved.length,payload.length);
 assert.equal(createHash("sha256").update(saved).digest("hex"),digest);
 assert.deepEqual(saved,payload);
 assert.equal(reqs.filter(x=>x.path===validRefPath&&x.method==="GET").length,1);
 assert.equal(reqs.filter(x=>x.path===validContentPath&&x.method==="GET").length,1);
 checks.push("SUCCEEDED row resolves the same-origin Artifact reference and Edge saves exact attachment bytes/hash/length");

 await evaluate("(()=>{const li=[...document.querySelectorAll('li')].find(x=>x.innerText.includes("+JSON.stringify(ids.badRequest)+"));const b=[...li.querySelectorAll('button')].find(x=>x.innerText.trim()==='下载文件');b.click();return true})()");
 await waitFor("document.querySelector('[role=alert]')?.innerText.includes('暂时无法获取输出文件')","invalid cross-project reference");
 const badContentPath="/api/v1/projects/"+ids.otherProject+"/documents/"+ids.badDocument+"/versions/"+ids.badVersion+"/content";
 assert.equal(reqs.filter(x=>x.path===badContentPath&&x.method==="GET").length,0);
 checks.push("cross-project reference fails before any content request or additional save");

 assert.ok(reqs.every(x=>x.path.startsWith("/api/v1/")),"observed API requests stayed on synthetic same-origin server");
 const summary={wbs:"OUT-01-A01-P39",status:"PASS_SCOPE_LIMITED",browser:"Microsoft Edge headless",
  runner_os:"GitHub hosted Windows Server 2025",runner_drive:"D:",synthetic_data:true,controlled_api:true,
  checks,api_requests:reqs.map(x=>({method:x.method,path:x.path,status:x.status})),
  saved_bytes:saved.length,saved_sha256:digest,customer_data:false,external_api_calls:0,
  plugin_executed:false,formal_license_trust:false,backend_live:false,release_eligible:false};
 await writeFile(summaryPath,JSON.stringify(summary,null,2)+"\n","utf8");console.log(JSON.stringify(summary));
}catch(error){console.error(JSON.stringify({error:String(error),requests:reqs.slice(-30)},null,2));process.exitCode=1}
finally{
 if(socket&&socket.readyState===WebSocket.OPEN)socket.close();
 edge.kill();await pause(300);
 await rm(profile,{recursive:true,force:true});await rm(downloadDir,{recursive:true,force:true});
 await new Promise(ok=>server.close(()=>ok()));
}