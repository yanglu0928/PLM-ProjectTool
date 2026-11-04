import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, writeFile, mkdtemp, rm, stat } from "node:fs/promises";
import { extname, join, resolve, sep, parse } from "node:path";
import { spawn } from "node:child_process";

const args=process.argv.slice(2);
function arg(name){const i=args.indexOf(name);return i<0?null:args[i+1]}
const dist=resolve(arg("--dist")||"");
const summaryPath=resolve(arg("--summary-out")||"");
if(!arg("--dist")||!arg("--summary-out"))throw new Error("--dist and --summary-out are required");
const runnerTemp=resolve(process.env.RUNNER_TEMP||"");
if(!runnerTemp||parse(runnerTemp).root.toLowerCase()!=="d:\\")throw new Error("GitHub hosted runner temp must be on D:");
if(!(await stat(join(dist,"index.html"))).isFile())throw new Error("frontend dist index.html missing");

const ids={project:"01234567-89ab-4cde-8123-456789abcdef",
 requirement:"11234567-89ab-4cde-8123-456789abcdef",
 version:"21234567-89ab-4cde-8123-456789abcdef",
 actor:"31234567-89ab-4cde-8123-456789abcdef",
 request:"41234567-89ab-4cde-8123-456789abcdef",
 job:"51234567-89ab-4cde-8123-456789abcdef"};
const now="2026-11-05T00:00:00Z", csrf="a".repeat(64), trace=ids.actor;
const reqs=[];let mode="accepted";
const root={requirement_id:ids.requirement,project_id:ids.project,requirement_code:"REQ-SYN-001",
 state:"ACTIVE",current_approved_version_ref:ids.version,created_by:ids.actor,created_at:now,
 updated_by:null,updated_at:now,etag:"\"v1\""};
function declared(){return {sources:0,acceptance_criteria:0,capability_assessments:0,assumptions:0,exclusions:0,dependencies:0,ai_tasks:0}}
function version(state){
 return {requirement_version_id:ids.version,requirement_id:ids.requirement,project_id:ids.project,version_no:1,
  state,title:"Synthetic approved requirement",domain_name:"Synthetic domain",priority:"HIGH",risk:"LOW",
  classification:"STANDARD_FUNCTION",content_fingerprint:"a".repeat(64),declared_counts:declared(),
  supersedes_version_ref:null,review_ref:null,review_round_ref:null,created_by:ids.actor,created_at:now,
  statement:"Synthetic requirement only",rationale:"Synthetic fixture",sources:[],acceptance_criteria:[],
  capability_assessments:[],assumptions:[],exclusions:[],dependencies:[],ai_tasks:[]};
}
function summary(state){
 const v=version(state);
 return {requirement_version_id:v.requirement_version_id,requirement_id:v.requirement_id,project_id:v.project_id,
  version_no:v.version_no,state:v.state,title:v.title,domain_name:v.domain_name,priority:v.priority,risk:v.risk,
  classification:v.classification,content_fingerprint:v.content_fingerprint,declared_counts:v.declared_counts,
  supersedes_version_ref:v.supersedes_version_ref,review_ref:v.review_ref,review_round_ref:v.review_round_ref,
  created_by:v.created_by,created_at:v.created_at};
}
function envelope(data,status=200){
 return {status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"},
  body:JSON.stringify(status>=400?{error:{code:data},trace_id:trace}:{data,trace_id:trace})};
}
function hasSession(req){return (req.headers.cookie||"").includes("plm_synthetic_session=accepted")}
function api(req,url){
 const method=req.method||"GET",path=url.pathname;
 const entry={method,path,query:url.search,headers:{
  csrf_present:Boolean(req.headers["x-csrf-token"]),idempotency_key_present:Boolean(req.headers["idempotency-key"]),
  content_type:req.headers["content-type"]||null},body:"",status:null};
 req.__p24Entry=entry;reqs.push(entry);
 if(path==="/api/v1/auth/login"&&method==="POST"){
  return {stream:true,collect:async()=>new Promise(resolveBody=>{let raw="";req.on("data",b=>raw+=b);req.on("end",()=>resolveBody(raw))})};
 }
 if(path.startsWith("/api/")&&!hasSession(req))return envelope("AUTH_SESSION_EXPIRED",401);
 const base="/api/v1/projects/"+ids.project;
 if(path===base+"/requirements/"+ids.requirement&&method==="GET")return envelope(root);
 if(path===base+"/requirements/"+ids.requirement+"/versions"&&method==="GET"){
  return envelope({items:[summary(mode==="unapproved"?"DRAFT":"APPROVED")],next_cursor:null,has_more:false});
 }
 if(path===base+"/requirements/"+ids.requirement+"/versions/"+ids.version&&method==="GET")
  return envelope(version(mode==="unapproved"?"DRAFT":"APPROVED"));
 if(path===base+"/output-requests"&&method==="POST"){
  let raw="";return {stream:true,collect:async()=>new Promise(resolveBody=>{req.on("data",b=>raw+=b);req.on("end",()=>{entry.body=raw;resolveBody(raw)})})};
 }
 if(path===base+"/output-requests"&&method==="GET")return envelope({items:[],next_cursor:null,has_more:false});
 return envelope("RESOURCE_NOT_FOUND",404);
}

const mime={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",
 ".css":"text/css; charset=utf-8",".svg":"image/svg+xml",".png":"image/png",".woff2":"font/woff2",".json":"application/json"};
const server=createServer(async(req,res)=>{
 res.on("finish",()=>{if(req.__p24Entry)req.__p24Entry.status=res.statusCode});
 const url=new URL(req.url||"/","http://localhost");
 try{
  if(url.pathname.startsWith("/api/")){
   const result=api(req,url);
   if(result?.stream){
    const raw=await result.collect();let body;try{body=JSON.parse(raw)}catch{body=null}
    if(url.pathname==="/api/v1/auth/login"){
     if(body?.username!=="synthetic-user"||body?.password!=="synthetic-only"){
      const out=envelope("AUTH_INVALID_CREDENTIALS",401);res.writeHead(out.status,out.headers);res.end(out.body);return;
     }
     const out=envelope({user:{user_id:ids.actor,username_display:"Synthetic hosted user"},deployment_role:"NONE",
      password_change_required:false,authorized_projects:[{project_id:ids.project,name:"Synthetic project",role:"PROJECT_MANAGER"}],
      absolute_expires_at:"2030-01-01T12:00:00Z",idle_expires_at:"2030-01-01T11:00:00Z",csrf_token:csrf});
     res.writeHead(out.status,{...out.headers,"Set-Cookie":"plm_synthetic_session=accepted; Path=/; HttpOnly; SameSite=Lax"});
     res.end(out.body);return;
    }
    if(url.pathname==="/api/v1/projects/"+ids.project+"/output-requests"&&req.method==="POST"){
     const expected={output_type:"DOCX",template_version_ref:"a1272ce0-01f0-5e6c-9706-000000000001",
      source_version_refs:[ids.version],output_policy_ref:"output.policy.requirement-docx.v1",plugin_operation:"word.generate"};
     if(req.headers["x-csrf-token"]!==csrf||!req.headers["idempotency-key"]||
       JSON.stringify(body)!==JSON.stringify(expected)){
      const out=envelope("VALIDATION_FAILED",422);res.writeHead(out.status,out.headers);res.end(out.body);return;
     }
     if(mode==="untrusted"){
      const out=envelope("SYSTEM_UNAVAILABLE",503);res.writeHead(out.status,out.headers);res.end(out.body);return;
     }
     const out=envelope({output_request_id:ids.request,job_id:ids.job,state:"QUEUED"},202);
     res.writeHead(out.status,out.headers);res.end(out.body);return;
    }
   }
   res.writeHead(result.status,result.headers);res.end(result.body);return;
  }
  let pathname=decodeURIComponent(url.pathname);if(pathname==="/")pathname="/index.html";
  let file=resolve(dist,"."+pathname);if(file!==dist&&!file.startsWith(dist+sep))throw new Error("static path escape");
  try{await stat(file)}catch{file=join(dist,"index.html")}
  const body=await readFile(file);
  res.writeHead(200,{"Content-Type":mime[extname(file)]||"application/octet-stream","Cache-Control":"no-store"});res.end(body);
 }catch(error){res.writeHead(500,{"Content-Type":"text/plain"});res.end(String(error))}
});
await new Promise((ok,bad)=>{server.once("error",bad);server.listen(0,"127.0.0.1",ok)});
const address=server.address(),origin="http://localhost:"+address.port;
const profile=await mkdtemp(join(runnerTemp,"plm-out-p24-edge-"));
const port=12000+(process.pid%30000);
const edge=spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",[
 "--headless=new","--disable-background-networking","--disable-sync","--remote-debugging-address=127.0.0.1",
 "--remote-debugging-port="+port,"--user-data-dir="+profile,"--no-first-run","--window-size=1450,1100",origin+"/login"
],{stdio:"ignore",windowsHide:true});
const pause=ms=>new Promise(resolvePause=>setTimeout(resolvePause,ms));
let socket,nextId=0;const pending=new Map();const checks=[];
async function getPage(){
 for(let i=0;i<300;i++){try{const entries=await(await fetch("http://127.0.0.1:"+port+"/json/list")).json();
  const page=entries.find(x=>x.type==="page"&&x.url.startsWith(origin));if(page)return page}catch{}await pause(100)}
 throw new Error("Edge browser target did not appear");
}
function send(method,params={}){const id=++nextId;socket.send(JSON.stringify({id,method,params}));
 return new Promise((resolveSend,rejectSend)=>pending.set(id,{resolveSend,rejectSend}))}
async function evaluate(expression){const out=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});
 if(out.exceptionDetails)throw new Error(out.exceptionDetails.text);return out.result.value}
async function waitFor(expression,label){for(let i=0;i<300;i++){try{if(await evaluate("Boolean("+expression+")"))return}catch{}await pause(100)}
 throw new Error("timeout "+label+": "+JSON.stringify(await evaluate("({url:location.href,text:document.body.innerText.slice(0,1800)})")))}
async function click(label){
 const ok=await evaluate("(()=>{const e=[...document.querySelectorAll('button,a')].find(x=>x.textContent.trim()==="+JSON.stringify(label)+");if(!e)return false;e.click();return true})()");
 if(!ok)throw new Error("missing browser action: "+label);
}
async function setValue(selector,value){
 const ok=await evaluate("(()=>{const e=document.querySelector("+JSON.stringify(selector)+");if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,"+JSON.stringify(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 if(!ok)throw new Error("missing browser input: "+selector);
}
async function navigate(path){await evaluate("history.pushState({},'',"+JSON.stringify(path)+");dispatchEvent(new PopStateEvent('popstate'))")}
async function openRequirement(){
 await navigate("/projects/"+ids.project+"/output-requests");
 await waitFor("location.pathname==='/projects/"+ids.project+"/output-requests'","output history route");
 await navigate("/projects/"+ids.project+"/requirements/"+ids.requirement);
 await waitFor("document.body.innerText.includes('固定版本')","requirement detail");
 await click("查看版本 1 的详情与原文入口");
 await waitFor("document.querySelector('#output-create-title')","selected requirement version");
}
try{
 const page=await getPage();socket=new WebSocket(page.webSocketDebuggerUrl);
 await new Promise((ok,bad)=>{socket.addEventListener("open",ok,{once:true});socket.addEventListener("error",bad,{once:true})});
 socket.addEventListener("message",({data})=>{const msg=JSON.parse(data);if(!msg.id||!pending.has(msg.id))return;
  const p=pending.get(msg.id);pending.delete(msg.id);if(msg.error)p.rejectSend(new Error(msg.error.message));else p.resolveSend(msg.result)});
 await send("Runtime.enable");await send("Page.enable");
 await waitFor("document.querySelector('#login-username')","login form");
 await setValue("#login-username","synthetic-user");await setValue("#login-password","synthetic-only");
 await click("登录 / 重新登录");await waitFor("document.body.innerText.includes('登录成功。')","synthetic login");
 await openRequirement();
 await click("请求生成 DOCX");
 await waitFor("document.body.innerText.includes('请求已受理')","accepted request receipt");
 assert.equal(reqs.filter(x=>x.method==="POST"&&x.path==="/api/v1/projects/"+ids.project+"/output-requests").length,1);
 const post=reqs.find(x=>x.method==="POST"&&x.path.endsWith("/output-requests"));
 assert.equal(post.headers.csrf_present,true);assert.equal(post.headers.idempotency_key_present,true);
 assert.deepEqual(JSON.parse(post.body),{output_type:"DOCX",template_version_ref:"a1272ce0-01f0-5e6c-9706-000000000001",
  source_version_refs:[ids.version],output_policy_ref:"output.policy.requirement-docx.v1",plugin_operation:"word.generate"});
 assert.ok(await evaluate("document.body.innerText.includes('请求受理不代表文件已生成')"));
 checks.push("approved fixed version submits the exact DOCX contract with CSRF and one idempotency key; receipt does not claim a file");
 await click("查看输出请求历史");
 await waitFor("location.pathname==='/projects/"+ids.project+"/output-requests'","output request history navigation");
 checks.push("accepted receipt navigates to the project output-request history route");

 mode="untrusted";await openRequirement();await click("请求生成 DOCX");
 await waitFor("document.querySelector('[role=alert]')?.innerText.includes('输出服务暂不可用')","simulated publisher-trust rejection");
 assert.equal(reqs.filter(x=>x.method==="POST"&&x.path.endsWith("/output-requests")).length,2);
 assert.equal(await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='请求生成 DOCX')"),false);
 checks.push("simulated untrusted-publisher service rejection is shown safely with no automatic retry");

 mode="unapproved";await openRequirement();
 assert.equal(await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='请求生成 DOCX')"),false);
 checks.push("non-approved version has no request action");

 assert.ok(reqs.every(x=>x.path.startsWith("/api/v1/")),"all API calls remain on synthetic same-origin API");
 const summary={wbs:"OUT-01-A01-P24",status:"PASS_SCOPE_LIMITED",browser:"Microsoft Edge headless",
  runner_os:"GitHub hosted Windows Server 2025",runner_drive:"D:",synthetic_data:true,controlled_api:true,
  checks,request_posts:reqs.filter(x=>x.method==="POST"&&x.path.endsWith("/output-requests")).length,
  customer_data:false,external_api_calls:0,plugin_executed:false,docx_generated:false,formal_license_trust:false,
  gate3_changed:false,pilot_ready:false,release_eligible:false};
 await writeFile(summaryPath,JSON.stringify(summary,null,2)+"\n","utf8");console.log(JSON.stringify(summary));
}catch(error){console.error(JSON.stringify({error:String(error),requests:reqs.slice(-30).map(x=>({method:x.method,path:x.path,query:x.query,status:x.status,headers:x.headers}))},null,2));process.exitCode=1}
finally{if(socket&&socket.readyState===WebSocket.OPEN)socket.close();edge.kill();await pause(300);
 await rm(profile,{recursive:true,force:true});await new Promise(ok=>server.close(()=>ok()));}
