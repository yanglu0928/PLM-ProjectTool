import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, writeFile, mkdtemp, rm, stat } from "node:fs/promises";
import { extname, join, resolve, sep, parse } from "node:path";
import { tmpdir } from "node:os";
import { spawn } from "node:child_process";

const args=process.argv.slice(2);
function arg(name){const i=args.indexOf(name);return i<0?null:args[i+1]}
const dist=resolve(arg("--dist")||"");
const summaryPath=resolve(arg("--summary-out")||"");
if(!arg("--dist")||!arg("--summary-out")) throw new Error("--dist and --summary-out are required");
const runnerTemp=resolve(process.env.RUNNER_TEMP||"");
if(!runnerTemp||parse(runnerTemp).root.toLowerCase()!=="d:\\") throw new Error("GitHub hosted runner temp must be on D:");
const distStat=await stat(join(dist,"index.html")); if(!distStat.isFile()) throw new Error("frontend dist index.html missing");
const ids={
 project:"01234567-89ab-4cde-8123-456789abcdef",
 foreignProject:"11234567-89ab-4cde-8123-456789abcdef",
 analysis:"21234567-89ab-4cde-8123-456789abcdef",
 version:"31234567-89ab-4cde-8123-456789abcdef",
 targetItem:"41234567-89ab-4cde-8123-456789abcdef",
 owner:"51234567-89ab-4cde-8123-456789abcdef",
 doc:"61234567-89ab-4cde-8123-456789abcdef",
 docVersion:"71234567-89ab-4cde-8123-456789abcdef",
 evidence:"81234567-89ab-4cde-8123-456789abcdef",
 trace:"91234567-89ab-4cde-8123-456789abcdef",
 analysisAction:"a1234567-89ab-4cde-8123-456789abce",
 humanAction:"b1234567-89ab-4cde-8123-456789abce",
 expiredAction:"c1234567-89ab-4cde-8123-456789abce",
 foreignAction:"d1234567-89ab-4cde-8123-456789abce"
};
const now="2026-11-02T00:00:00Z", csrf="a".repeat(64), trace=ids.trace;
const requests=[];
const itemCursor="synthetic-next."+ "b".repeat(43);
const sourceSummary=(actionId,sourceKind,title)=>({
 action_item_id:actionId,source_kind:sourceKind,action_type:"CONFIRM_DECISION",title,owner_ref:ids.owner,
 due_at:"2026-12-01T00:00:00Z",priority:"HIGH",action_state:"SUBMITTED",submitted_at:now,verified_at:null,
 closed_at:null,resolution_trace_ref:null,updated_at:now,etag:"\"v2\""
});
const actionSummaries=[
 sourceSummary(ids.analysisAction,"ANALYSIS_ITEM","Synthetic analysis action"),
 sourceSummary(ids.humanAction,"HUMAN","Synthetic human action"),
 sourceSummary(ids.expiredAction,"ANALYSIS_ITEM","Synthetic unavailable source action"),
 sourceSummary(ids.foreignAction,"ANALYSIS_ITEM","Synthetic cross-project source action")
];
function actionDetail(actionId){
 const summary=actionSummaries.find(x=>x.action_item_id===actionId);
 const human=summary?.source_kind==="HUMAN";
 if(!summary)return null;
 return {...summary,source_analysis_version_ref:human?null:ids.version,source_item_id:human?null:ids.targetItem,
  human_source_reason:human?"Synthetic meeting note without a fixed document anchor":null,
  requested_input_spec:{fields:[{name:"Synthetic input",format:"text",example:"synthetic only",required:true}]},
  responses:[],evidence:[],created_by:ids.owner,created_reason:"Synthetic handover acceptance fixture",
  created_at:now,verified_by:null,current_event:{action_state_event_id:ids.trace,sequence_no:2,
   from_state:"IN_PROGRESS",to_state:"SUBMITTED",actor_id:ids.owner,reason:"Synthetic submitted response",occurred_at:now}};
}
const analysis={handover_analysis_id:ids.analysis,project_id:ids.project,analysis_purpose:"Synthetic handover source navigation",
 source_set_ref:"sha256:"+"a".repeat(64),state:"ACTIVE",current_approved_version_ref:null,
 created_by:ids.owner,created_at:now,updated_at:now,etag:"\"v0\""};
const versionSummary={handover_analysis_version_id:ids.version,handover_analysis_id:ids.analysis,project_id:ids.project,
 version_no:1,state:"DRAFT",source_set_ref:"sha256:"+"a".repeat(64),capability_baseline_id:ids.owner,
 capability_baseline_version_ref:ids.trace,content_fingerprint:"b".repeat(64),declared_source_count:1,
 declared_item_count:201,declared_evidence_count:0,declared_capability_ref_count:0,declared_ai_task_count:0,
 supersedes_version_ref:null,review_ref:null,review_round_ref:null,created_by:ids.owner,created_at:now,
 source_documents:[],ai_tasks:[]};
const versionDetail={...versionSummary,source_documents:[{document_id:ids.doc,document_version_id:ids.docVersion,ordinal:0}]};
function analysisItem(itemId,ordinal,title){
 return {analysis_item_id:itemId,handover_analysis_version_id:ids.version,handover_analysis_id:ids.analysis,project_id:ids.project,
  ordinal,item_type:"NEED_CONFIRM",title,statement:"Synthetic source statement",impact:"Synthetic impact",
  severity:"HIGH",priority:"URGENT",recommendation:"Use only the fixed synthetic source",
  confirmation_question:"Synthetic confirmation question",
  required_input_spec:{fields:[{name:"Deployment scope",format:"text",example:"synthetic example",required:true}]},
  source_missing:false,state:"CANDIDATE",evidence_refs:[],capability_refs:[],options:[]};
}
const fillers=Array.from({length:200},(_,i)=>{
 const hex=(i+1).toString(16).padStart(8,"0");
 return analysisItem(hex+"-0000-4000-8000-"+(i+1).toString(16).padStart(12,"0"),i,"Synthetic filler "+String(i+1));
});
const target=analysisItem(ids.targetItem,200,"Synthetic exact source issue");
function envelope(data,status=200){
 return {status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"},
  body:JSON.stringify(status>=400?{error:{code:data,message:"Synthetic controlled error"},trace_id:trace}:{data,trace_id:trace})};
}
function requireSession(req){return (req.headers.cookie||"").includes("plm_synthetic_session=accepted")}
function api(req,url){
 const method=req.method||"GET", path=url.pathname;
 requests.push({method,path,query:url.search});
 if(path==="/api/v1/auth/login"&&method==="POST"){
  let raw=""; return {stream:true,collect:async()=>new Promise(resolveBody=>{req.on("data",b=>raw+=b);req.on("end",()=>resolveBody(raw))})};
 }
 if(path.startsWith("/api/")&&!requireSession(req)) return envelope("AUTH_SESSION_EXPIRED",401);
 if(path==="/api/v1/projects/"+ids.project+"/handover-action-items"&&method==="GET")
  return envelope({items:actionSummaries,next_cursor:null,has_more:false});
 const detailMatch=path.match(/^\/api\/v1\/projects\/([^/]+)\/handover-action-items\/([^/]+)$/);
 if(detailMatch&&method==="GET"&&detailMatch[1]===ids.project){
  const value=actionDetail(detailMatch[2]); return value?envelope(value):envelope("RESOURCE_NOT_FOUND",404);
 }
 const sourceMatch=path.match(/^\/api\/v1\/projects\/([^/]+)\/handover-action-items\/([^/]+)\/source-location$/);
 if(sourceMatch&&method==="GET"&&sourceMatch[1]===ids.project){
  const id=sourceMatch[2];
  if(id===ids.expiredAction)return envelope("RESOURCE_NOT_FOUND",404);
  if(id===ids.foreignAction)return envelope({source_kind:"ANALYSIS_ITEM",resolution_state:"LOCATABLE",
    target:{project_id:ids.foreignProject,handover_analysis_id:ids.analysis,handover_analysis_version_id:ids.version,
     analysis_item_id:ids.targetItem},unavailable_reason:null});
  if(id===ids.analysisAction)return envelope({source_kind:"ANALYSIS_ITEM",resolution_state:"LOCATABLE",
   target:{project_id:ids.project,handover_analysis_id:ids.analysis,handover_analysis_version_id:ids.version,
    analysis_item_id:ids.targetItem},unavailable_reason:null});
  return envelope("RESOURCE_NOT_FOUND",404);
 }
 const base="/api/v1/projects/"+ids.project+"/handover-analyses/"+ids.analysis;
 if(method==="GET"&&path===base)return envelope(analysis);
 if(method==="GET"&&path===base+"/versions")return envelope({items:[versionSummary],next_cursor:null,has_more:false});
 if(method==="GET"&&path===base+"/versions/"+ids.version)return envelope(versionDetail);
 if(method==="GET"&&path===base+"/versions/"+ids.version+"/items"){
  const cursor=new URLSearchParams(url.search).get("cursor");
  return cursor===itemCursor?envelope({items:[target],next_cursor:null,has_more:false})
   :envelope({items:fillers,next_cursor:itemCursor,has_more:true});
 }
 return envelope("RESOURCE_NOT_FOUND",404);
}
const mime={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",
 ".svg":"image/svg+xml",".png":"image/png",".woff2":"font/woff2",".json":"application/json"};
const server=createServer(async(req,res)=>{
 const url=new URL(req.url||"/","http://localhost");
 try{
  if(url.pathname.startsWith("/api/")){
   const result=api(req,url);
   if(result?.stream){
    const raw=await result.collect();
    let credentials;try{credentials=JSON.parse(raw)}catch{credentials=null}
    if(credentials?.username!=="synthetic-user"||credentials?.password!=="synthetic-only"){
     const out=envelope("AUTH_INVALID_CREDENTIALS",401);res.writeHead(out.status,out.headers);res.end(out.body);return;
    }
    const out=envelope({user:{user_id:ids.owner,username_display:"Synthetic hosted user"},deployment_role:"NONE",
     password_change_required:false,authorized_projects:[{project_id:ids.project,name:"Synthetic project",role:"PROJECT_MANAGER"}],
     absolute_expires_at:"2030-01-01T12:00:00Z",idle_expires_at:"2030-01-01T11:00:00Z",csrf_token:csrf});
    res.writeHead(out.status,{...out.headers,"Set-Cookie":"plm_synthetic_session=accepted; Path=/; HttpOnly; SameSite=Lax"});
    res.end(out.body);return;
   }
   res.writeHead(result.status,result.headers);res.end(result.body);return;
  }
  let pathname=decodeURIComponent(url.pathname);if(pathname==="/")pathname="/index.html";
  let file=resolve(dist,"."+pathname);
  if(file!==dist&&!file.startsWith(dist+sep))throw new Error("static path escape");
  let body;try{body=await readFile(file)}catch{body=await readFile(join(dist,"index.html"));file=join(dist,"index.html")}
  res.writeHead(200,{"Content-Type":mime[extname(file)]||"application/octet-stream","Cache-Control":"no-store"});
  res.end(body);
 }catch(error){res.writeHead(500,{"Content-Type":"text/plain"});res.end(String(error))}
});
await new Promise((ok,bad)=>{server.once("error",bad);server.listen(0,"127.0.0.1",ok)});
const address=server.address();const origin="http://localhost:"+address.port;
const profile=await mkdtemp(join(tmpdir(),"plm-a50-edge-"));
const port=12000+(process.pid%30000);
const edge=spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",[
 "--headless=new","--disable-background-networking","--disable-sync","--remote-debugging-address=127.0.0.1",
 "--remote-debugging-port="+port,"--user-data-dir="+profile,"--no-first-run","--window-size=1450,1100",origin+"/login"
],{stdio:"ignore",windowsHide:true});
const pause=ms=>new Promise(resolvePause=>setTimeout(resolvePause,ms));
let socket,nextId=0;const pending=new Map();
async function getPage(){
 for(let i=0;i<300;i++){try{const entries=await(await fetch("http://127.0.0.1:"+port+"/json/list")).json();
  const page=entries.find(x=>x.type==="page"&&x.url.startsWith(origin));if(page)return page}catch{}
  await pause(100)}
 throw new Error("Edge browser target did not appear");
}
function send(method,params={}){const id=++nextId;socket.send(JSON.stringify({id,method,params}));
 return new Promise((resolveSend,rejectSend)=>pending.set(id,{resolveSend,rejectSend}))}
async function evaluate(expression){const out=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});
 if(out.exceptionDetails)throw new Error(out.exceptionDetails.text);return out.result.value}
async function waitFor(expression,label){for(let i=0;i<300;i++){try{if(await evaluate("Boolean("+expression+")"))return}catch{}await pause(100)}
 throw new Error("timeout "+label+": "+JSON.stringify(await evaluate("({url:location.href,text:document.body.innerText.slice(0,2500)})")))}
async function click(text){
 const ok=await evaluate("(()=>{const e=[...document.querySelectorAll('button,a')].find(x=>x.textContent.trim()==="+JSON.stringify(text)+");if(!e)return false;e.click();return true})()");
 if(!ok)throw new Error("missing browser action: "+text);
}
async function setValue(selector,value){
 const ok=await evaluate("(()=>{const e=document.querySelector("+JSON.stringify(selector)+");if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,"+JSON.stringify(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 if(!ok)throw new Error("missing browser input: "+selector);
}
async function navigate(path){
 await evaluate("history.pushState({},'',"+JSON.stringify(path)+");dispatchEvent(new PopStateEvent('popstate'))");
}
async function clickActionDetail(actionId){
 const ok=await evaluate("(()=>{const li=[...document.querySelectorAll('li')].find(e=>e.innerText.includes("+JSON.stringify(actionId===""+ids.analysisAction?"Synthetic analysis action":actionId===ids.humanAction?"Synthetic human action":actionId===ids.expiredAction?"Synthetic unavailable source action":"Synthetic cross-project source action")+"));const b=[...li?.querySelectorAll('button')||[]].find(x=>x.textContent.trim()==='查看待办详情');if(!b)return false;b.click();return true})()");
 if(!ok)throw new Error("action item row/button missing: "+actionId);
}
const checks=[];
try{
 const page=await getPage();socket=new WebSocket(page.webSocketDebuggerUrl);
 await new Promise((ok,bad)=>{socket.addEventListener("open",ok,{once:true});socket.addEventListener("error",bad,{once:true})});
 socket.addEventListener("message",({data})=>{const msg=JSON.parse(data);if(!msg.id||!pending.has(msg.id))return;
  const p=pending.get(msg.id);pending.delete(msg.id);if(msg.error)p.rejectSend(new Error(msg.error.message));else p.resolveSend(msg.result)});
 await send("Runtime.enable");await send("Page.enable");
 await waitFor("document.querySelector('#login-username')","login form");
 await setValue("#login-username","synthetic-user");await setValue("#login-password","synthetic-only");
 await click("登录 / 重新登录");await waitFor("document.body.innerText.includes('登录成功。')","synthetic login");
 const actionPath="/projects/"+ids.project+"/handover-actions?actionId="+ids.analysisAction;
 await navigate(actionPath);
 await waitFor("document.body.innerText.includes('Synthetic analysis action')&&document.body.innerText.includes('已提交待验证')","action detail");
 await click("定位原始问题和文档位置");
 await waitFor("[...document.querySelectorAll('a')].some(x=>x.textContent.trim()==='打开原始问题与证据位置')","fixed source link");
 await evaluate("window.__a50ScrollTarget=null;const old=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=function(){window.__a50ScrollTarget=this.id||this.tagName;if(old)old.call(this,{block:'center'})}");
 await click("打开原始问题与证据位置");
 await waitFor("location.pathname==='/projects/"+ids.project+"/handover/"+ids.analysis+"'&&new URLSearchParams(location.search).get('fixedVersionId')==='"+ids.version+"'&&new URLSearchParams(location.search).get('sourceItemId')==='"+ids.targetItem+"'&&document.getElementById('handover-item-"+ids.targetItem+"')","fixed version exact source page");
 await waitFor("window.__a50ScrollTarget==='handover-item-"+ids.targetItem+"'","target issue scrolled into view");
 checks.push("analysis action navigates to fixed version and finds item on second page");
 assert.equal(requests.filter(x=>x.path.endsWith("/handover-action-items/"+ids.analysisAction+"/source-location")).length,1);
 assert.equal(requests.filter(x=>x.path.endsWith("/handover-analyses/"+ids.analysis+"/versions/"+ids.version+"/items")).length,2);
 await navigate("/projects/"+ids.project+"/handover-actions?actionId="+ids.humanAction);
 await waitFor("document.body.innerText.includes('Synthetic human action')&&document.body.innerText.includes('人工来源没有固定文档锚点')","HUMAN source");
 assert.equal(await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='定位原始问题和文档位置')"),false);
 assert.equal(requests.filter(x=>x.path.endsWith("/handover-action-items/"+ids.humanAction+"/source-location")).length,0);
 checks.push("HUMAN source is visible without a fabricated locator or API call");
 await navigate("/projects/"+ids.project+"/handover-actions?actionId="+ids.foreignAction);
 await waitFor("document.body.innerText.includes('Synthetic cross-project source action')","cross-project action detail");
 await click("定位原始问题和文档位置");await waitFor("document.querySelector('[role=alert]')","cross-project rejection");
 assert.equal(await evaluate("[...document.querySelectorAll('a')].some(x=>x.textContent.trim()==='打开原始问题与证据位置')"),false);
 assert.ok(await evaluate("document.body.innerText.includes('Synthetic cross-project source action')&&document.body.innerText.includes('已提交待验证')"));
 checks.push("cross-project target rejected while action state is preserved");
 await navigate("/projects/"+ids.project+"/handover-actions?actionId="+ids.expiredAction);
 await waitFor("document.body.innerText.includes('Synthetic unavailable source action')","unavailable action detail");
 await click("定位原始问题和文档位置");await waitFor("document.querySelector('[role=alert]')","unavailable source");
 assert.equal(await evaluate("[...document.querySelectorAll('a')].some(x=>x.textContent.trim()==='打开原始问题与证据位置')"),false);
 assert.ok(await evaluate("document.body.innerText.includes('Synthetic unavailable source action')&&document.body.innerText.includes('已提交待验证')"));
 checks.push("missing/expired source fails closed without clearing Action detail");
 const apiPaths=requests.filter(x=>x.path.startsWith("/api/")).map(x=>x.path);
 assert.ok(apiPaths.every(x=>x.startsWith("/api/v1/")),"all browser requests remain on the synthetic same-origin API");
 const summary={wbs:"PLT-PKG-01-A09-P51-A50-E01",status:"PASS_LIMITED",browser:"Microsoft Edge headless",
  runner_os:"GitHub hosted Windows Server 2025",runner_drive:"D:",synthetic_data:true,external_api_calls:0,
  checks,source_location_requests:requests.filter(x=>x.path.endsWith("/source-location")).length,
  fixed_item_pages:requests.filter(x=>x.path.endsWith("/items")).length,customer_data:false,formal_license_trust:false,
  gate3_changed:false,pilot_ready:false,release_eligible:false};
 await writeFile(summaryPath,JSON.stringify(summary,null,2)+"\n","utf8");console.log(JSON.stringify(summary));
}catch(error){console.error(JSON.stringify({error:String(error),requests:requests.slice(-40)},null,2));process.exitCode=1}
finally{
 if(socket&&socket.readyState===WebSocket.OPEN)socket.close();
 edge.kill();await pause(300);await rm(profile,{recursive:true,force:true});
 await new Promise(ok=>server.close(()=>ok()));
}
