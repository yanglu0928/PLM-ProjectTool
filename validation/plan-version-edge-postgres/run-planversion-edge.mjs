/** Owned Win11 Edge proof for PlanVersion requirement mapping, validation and review submission. */
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { join, resolve, sep } from "node:path";
import { tmpdir } from "node:os";

const [origin, project, plan] = process.argv.slice(2);
const username = process.env.PLM_BROWSER_SYNTHETIC_USERNAME;
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const reviewer = process.env.PLM_BROWSER_SYNTHETIC_REVIEWER;
const tempRoot = process.env.PLM_BROWSER_TEMP_ROOT;
const expectedRoot = "D:\\PLM-Test-Temp";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const checks = {
  origin: /^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? ""), project: uuid.test(project ?? ""),
  plan: uuid.test(plan ?? ""), username: username === "Edge PlanVersion Manager",
  password: typeof password === "string" && password.length >= 24,
  reviewer: reviewer === "Edge PlanVersion Reviewer",
  temp: resolve(tempRoot ?? "") === resolve(expectedRoot),
};
if (Object.values(checks).some(ok => !ok)) {
  throw new Error(`Owned synthetic PlanVersion inputs and D:\\PLM-Test-Temp are required (${JSON.stringify(checks)})`);
}
await mkdir(tempRoot, { recursive: true });
const profile = await mkdtemp(join(tempRoot, "plm-planversion-edge-profile-"));
const cdpPort = 10000 + process.pid % 40000;
const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const edge = spawn(edgePath, ["--headless=new", `--remote-debugging-port=${cdpPort}`,
  `--user-data-dir=${profile}`, "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--window-size=1440,1100", "about:blank"], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
let socket; let serial = 0; const pending = new Map(); const responses = []; const errors = [];
const requestById = new Map(); const responseByRequest = new Map(); const responseBodies = [];
function send(method, params = {}) {
  const id = ++serial; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, { resolve: resolveCall, reject: rejectCall }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Edge evaluation failed: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 300; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,2500),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; API=${JSON.stringify(responses.slice(-16).map(({url,status,request})=>({url,status,request})))}; bodies=${JSON.stringify(responseBodies.slice(-8))}; browser=${JSON.stringify(errors)}`);
}
async function clickText(label) {
  const ok = await evaluate(`(()=>{const e=[...document.querySelectorAll('button,a')].find(x=>x.textContent.trim()===${JSON.stringify(label)});if(!e||e.disabled)return false;e.click();return true})()`);
  if (!ok) throw new Error(`Missing or disabled action: ${label}`);
}
async function setValue(selector, value) {
  const ok = await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value')?.set;setter?setter.call(e,${JSON.stringify(value)}):e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);
  if (!ok) throw new Error(`Missing input ${selector}`);
}
async function check(selector) {
  const ok = await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;e.checked=true;e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);
  if (!ok) throw new Error(`Missing checkbox ${selector}`);
}
async function checkIndex(selector, index) {
  const ok = await evaluate(`(()=>{const e=document.querySelectorAll(${JSON.stringify(selector)})[${index}];if(!e)return false;e.checked=true;e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);
  if (!ok) throw new Error(`Missing checkbox index ${index}`);
}
async function loginAs(name) {
  await waitFor("document.querySelector('#login-username')", "real login form");
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await setValue("#login-username", name);
    await setValue("#login-password", password);
    await clickText("登录 / 重新登录");
    for (let n = 0; n < 100; n += 1) {
      if (await evaluate("document.body?.innerText?.includes('登录成功。')")) return;
      const latest = responses.filter(item => item.url.endsWith("/api/v1/auth/login")).at(-1);
      if (latest?.status === 503) break;
      await pause(100);
    }
    const latest = responses.filter(item => item.url.endsWith("/api/v1/auth/login")).at(-1);
    if (latest?.status !== 503 || attempt === 1) {
      throw new Error(`Real login did not initialize session/CSRF: ${JSON.stringify({status:latest?.status,body:await evaluate("document.body?.innerText?.slice(-800)")})}`);
    }
    await pause(500);
  }
}
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try { const pages = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = pages.find(item => item.type === "page"); if (page) return page; } catch { /* Edge starting */ }
    await pause(100);
  }
  throw new Error("Owned Edge CDP page did not start");
}
try {
  const page = await findPage(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolveCall, rejectCall) => { socket.addEventListener("open", resolveCall, { once: true }); socket.addEventListener("error", rejectCall, { once: true }); });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.id && pending.has(event.id)) { const task = pending.get(event.id); pending.delete(event.id); event.error ? task.reject(event.error) : task.resolve(event.result); }
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text ?? "browser exception");
    if (event.method === "Network.requestWillBeSent" && event.params.request.url.includes("/api/")) {
      requestById.set(event.params.requestId, { method: event.params.request.method,
        initiator: event.params.initiator?.type, frame: event.params.initiator?.stack?.callFrames?.[0]?.url });
    }
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      const response = event.params.response;
      const record = { url: response.url, status: response.status, headers: response.headers,
        request: requestById.get(event.params.requestId) };
      responses.push(record); responseByRequest.set(event.params.requestId, record);
    }
    if (event.method === "Network.loadingFinished" && responseByRequest.has(event.params.requestId)) {
      const record = responseByRequest.get(event.params.requestId);
      if (record.url.includes(`/plans/${plan}/versions/`)) void send("Network.getResponseBody", { requestId: event.params.requestId })
        .then(value => {
          const raw = value.base64Encoded ? Buffer.from(value.body, "base64").toString("utf8") : value.body;
          const payload = JSON.parse(raw);
          responseBodies.push({ url: record.url, status: record.status,
            contentType: record.headers["content-type"], cacheControl: record.headers["cache-control"],
            headerTrace: record.headers["x-trace-id"], bodyTrace: payload.trace_id,
            envelopeKeys: Object.keys(payload), dataKeys: Object.keys(payload.data ?? {}),
            versionId: payload.data?.plan_version_id, state: payload.data?.version_state,
            errorCode: payload.error?.code, detail: payload.detail });
        }).catch(error => responseBodies.push({ url: record.url, error: String(error) }));
    }
  });
  await send("Network.enable"); await send("Page.enable"); await send("Runtime.enable");
  await send("Page.navigate", { url: `${origin}/login` });
  await loginAs(username);
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(`/projects/${project}/plans/${plan}/versions/new`)});dispatchEvent(new PopStateEvent('popstate'))})()`);
  await waitFor("document.querySelector('input[name=\"approved-solution\"]')", "approved Outline candidate");
  await evaluate(`(()=>{const e=document.querySelector('input[name="approved-solution"]');e.checked=true;e.dispatchEvent(new Event('change',{bubbles:true}))})()`);
  await setValue("#task-name-0", "合成实施任务一"); await setValue("#task-acceptance-0", "任务一验收条件满足");
  await check('input[type="checkbox"]');
  await clickText("增加WBS任务");
  await setValue("#task-name-1", "合成实施任务二"); await setValue("#task-code-1", "TASK-002");
  await setValue("#task-acceptance-1", "任务二验收条件满足");
  const checkboxCount = await evaluate("document.querySelectorAll('input[type=checkbox]').length");
  if (checkboxCount < 2) throw new Error("Fixed requirement is not offered for the second WBS assignment");
  await checkIndex('input[type="checkbox"]', 1);
  await clickText("预览完整草稿"); await waitFor("document.body?.innerText?.includes('创建前预览')", "complete multi-task preview");
  await clickText("确认创建草稿版本");
  await waitFor("document.body?.innerText?.includes('草稿版本已创建：')", "create receipt visible");
  await evaluate(`(()=>{const original=window.fetch.bind(window);window.__plmVersionReadCalls=[];window.fetch=async(...args)=>{const response=await original(...args);const request=args[0] instanceof Request?args[0].url:String(args[0]);if(request.includes('/plans/${plan}/versions/')){const copy=response.clone();let payload=null;try{payload=await copy.json()}catch{}window.__plmVersionReadCalls.push({request,status:response.status,contentType:response.headers.get('content-type'),cacheControl:response.headers.get('cache-control'),headerTrace:response.headers.get('x-trace-id'),bodyTrace:payload?.trace_id,dataKeys:Object.keys(payload?.data??{}),versionId:payload?.data?.plan_version_id,errorCode:payload?.error?.code,errorMessage:payload?.error?.message})}return response}})()`);
  const detailHref = await evaluate("document.querySelector('a[href*=\"/versions/\"]')?.getAttribute('href')");
  if (!detailHref?.includes('/versions/')) throw new Error(`Missing created snapshot link: ${detailHref}`);
  await clickText("查看固定版本");
  await waitFor("document.body?.innerText?.includes('计划固定版本快照')", "snapshot route mounted");
  const readProbe = await evaluate(`(async()=>{const r=await fetch(${JSON.stringify(`/api/v1/projects/${project}/plans/${plan}/versions/${detailHref.split('/').at(-1)}`)},{credentials:'same-origin',cache:'no-store',redirect:'error',headers:{Accept:'application/json'}});const body=await r.json();let parser;try{const m=await import('/assets/planVersionReadClient-BbPVZkav.js');const client=new m.t(async()=>new Response(JSON.stringify(body),{status:r.status,headers:r.headers}),1000);await client.detail(${JSON.stringify(project)},${JSON.stringify(plan)},${JSON.stringify(detailHref.split('/').at(-1))});parser={ok:true}}catch(e){parser={ok:false,name:e?.name,code:e?.code,message:e?.message}}return {status:r.status,headers:Object.fromEntries(r.headers.entries()),body,parser}})()`);
  const readData = readProbe.body?.data ?? {};
  const uuidCheck = value => typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
  const exactKeys = (value, keys) => Object.keys(value ?? {}).length === keys.length && keys.every(key => Object.hasOwn(value ?? {}, key));
  const topKeys = ["plan_version_id", "plan_id", "project_id", "version_no", "version_state", "created_by", "supersedes_version_ref", "review_ref", "review_round_ref", "created_at", "calendar_ref", "approved_solution_refs", "wbs_items", "dependencies", "milestones", "exclusions"];
  const iso = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
  const maybeId = value => value === null || uuidCheck(value);
  readProbe.checks = {keys: exactKeys(readData, topKeys), ids: [readData.plan_version_id, readData.plan_id, readData.project_id, readData.created_by].every(uuidCheck), version: readData.plan_id === plan && readData.project_id === project && readData.version_state === "DRAFT" && Number.isSafeInteger(readData.version_no) && readData.version_no >= 1 && ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"].includes(readData.version_state), optionalIds: maybeId(readData.supersedes_version_ref) && maybeId(readData.review_ref) && maybeId(readData.review_round_ref), date: iso.test(readData.created_at ?? "") && Number.isFinite(Date.parse(readData.created_at)) && new Date(readData.created_at).toISOString().slice(0, 19) === readData.created_at.slice(0, 19), review: (readData.review_ref === null) === (readData.review_round_ref === null), calendar: readData.calendar_ref === null || /^[A-Z][A-Z0-9_]{0,127}$/.test(readData.calendar_ref), arrays: ["approved_solution_refs", "wbs_items", "dependencies", "milestones", "exclusions"].every(key => Array.isArray(readData[key]) && readData[key].every(value => typeof value === "object" && value !== null && !Array.isArray(value))), trace: readProbe.headers?.["x-trace-id"] === readProbe.body?.trace_id, noStore: readProbe.headers?.["cache-control"] === "no-store", noEtag: !Object.keys(readProbe.headers ?? {}).some(key => key.toLowerCase() === "etag")};
  readProbe.dataKeys = Object.keys(readData); readProbe.wbsKeys = Object.keys(readData.wbs_items?.[0] ?? {}); readProbe.failedChecks = Object.entries(readProbe.checks).filter(([, ok]) => !ok).map(([key]) => key); delete readProbe.body;
  if (readProbe.status !== 200) throw new Error(`PlanVersion GET probe failed: ${JSON.stringify(readProbe)}`);
  await pause(300);
  if (await evaluate("document.body?.innerText?.includes('暂时无法读取计划版本')")) throw new Error(`PlanVersion reader rejects HTTP 200 contract: ${JSON.stringify({url:await evaluate("location.pathname"),pageText:await evaluate("document.body?.innerText?.slice(-1200)"),windowCalls:await evaluate("window.__plmVersionReadCalls"),status:readProbe.status,headers:readProbe.headers,parser:readProbe.parser,failedChecks:readProbe.failedChecks,dataKeys:readProbe.dataKeys,planVersionCalls:responses.filter(item=>item.url.includes(`/plans/${plan}/versions/`)),responseBodies})}`);
  await waitFor("document.body?.innerText?.includes('核查此固定版本')", "created fixed version readback");
  const createdVersion = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(createdVersion)) throw new Error("Created PlanVersion ID is invalid");
  await clickText("核查此固定版本"); await waitFor("document.querySelector('button')?.textContent.includes('执行Validate')", "Validate page");
  await clickText("执行Validate"); await waitFor("document.body?.innerText?.includes('验证通过')||document.body?.innerText?.includes('发现阻断问题')", "validation report");
  if (await evaluate("document.body?.innerText?.includes('发现阻断问题')")) throw new Error("PlanVersion validation reported blockers");
  const uncovered = await evaluate(`(()=>{const text=document.body?.innerText??'';const m=text.match(/未覆盖需求\\s*(\\d+)/);return m?Number(m[1]):null})()`);
  if (uncovered !== 0) throw new Error(`Expected zero uncovered approved requirements, got ${uncovered}`);
  await clickText("返回固定版本"); await waitFor("document.body?.innerText?.includes('提交此计划版本评审')", "fixed version review action");
  await clickText("提交此计划版本评审"); await waitFor("document.body?.innerText?.includes('读取项目评审人')", "review submission page");
  await clickText("读取项目评审人"); await waitFor("document.querySelector('input[type=checkbox]')", "eligible synthetic customer reviewer");
  await check('input[type="checkbox"]');
  await evaluate(`(()=>{const e=[...document.querySelectorAll('input[type=checkbox]')].find(x=>x.closest('label')?.textContent.includes('确认提交'));if(!e)throw new Error('missing explicit review confirmation');e.checked=true;e.dispatchEvent(new Event('change',{bubbles:true}))})()`);
  await clickText("确认提交正式评审"); await waitFor("document.body?.innerText?.includes('已进入正式评审')", "atomic review receipt");
  await clickText("打开评审"); await waitFor("location.pathname.includes('/reviews/')", "Review detail route");
  const finalPath = await evaluate("location.pathname");
  await send("Page.navigate", { url: `${origin}/login` });
  await loginAs(reviewer);
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(finalPath)});dispatchEvent(new PopStateEvent('popstate'))})()`);
  await waitFor("document.body?.innerText?.includes('计划版本评审')||document.body?.innerText?.includes('评审意见')", "reviewer-readable review detail");
  if (errors.length) throw new Error(`Browser exceptions: ${JSON.stringify(errors)}`);
  const requiredStatuses = [201, 200];
  const planVersionWrites = responses.filter(item => item.url.includes(`/plans/${plan}/versions`));
  if (!requiredStatuses.every(status => planVersionWrites.some(item => item.status === status))) throw new Error(`Missing persisted Create/GET responses: ${JSON.stringify(planVersionWrites)}`);
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  await writeFile(join(tempRoot, `planversion-edge-${createdVersion}.png`), Buffer.from(screenshot.data, "base64"));
  console.log(`PLAN_VERSION_EDGE_PG_PASS: created=${createdVersion}; mapped fixed requirement to 2 WBS items; Validate PASS/zero uncovered; atomic submit reached IN_REVIEW; reviewer read ${finalPath}; API responses=${responses.length}`);
} finally {
  try { socket?.close(); } catch { /* Owned browser cleanup */ }
  edge.kill(); await pause(500);
  if (!resolve(profile).startsWith(resolve(tempRoot) + sep) || !resolve(tempRoot).startsWith(resolve(expectedRoot))) throw new Error("Unsafe Edge profile cleanup target");
  if (edge.exitCode === null && edge.signalCode === null) await Promise.race([new Promise(done => edge.once("exit", done)), pause(3000)]);
  await rm(profile, { recursive: true, force: true, maxRetries: 15, retryDelay: 200 });
}
