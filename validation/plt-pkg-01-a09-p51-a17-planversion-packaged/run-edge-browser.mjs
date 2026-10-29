/** Packaged HTTPS PlanVersion creation, validation and review submission proof. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { join, resolve, sep } from "node:path";

const [origin, project] = process.argv.slice(2);
const manager = process.env.PLM_P51_A17_MANAGER;
const reviewer = process.env.PLM_P51_A17_REVIEWER;
const password = process.env.PLM_P51_A17_PASSWORD;
const tempRoot = process.env.PLM_P51_A17_TEMP;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
let packagedOriginAllowed = false;
try {
  const parsedOrigin = new URL(origin ?? "");
  packagedOriginAllowed = parsedOrigin.protocol === "https:"
    && ["localhost", "plm.example.test"].includes(parsedOrigin.hostname)
    && parsedOrigin.origin === origin;
} catch { /* Reject malformed origins. */ }
if (!packagedOriginAllowed || !uuid.test(project ?? "")
  || manager !== "Synthetic Packaged User" || reviewer !== "Synthetic Handover Customer"
  || password !== "synthetic-packaged-login-password"
  || !tempRoot || resolve(tempRoot).toLowerCase().includes("\\\\")
  || resolve(tempRoot).toLowerCase().startsWith("c:\\")
  || resolve(process.env.RUNNER_TEMP ?? "") === resolve(tempRoot)
  || !resolve(tempRoot).toLowerCase().startsWith(resolve(process.env.RUNNER_TEMP ?? "").toLowerCase() + sep.toLowerCase())
  || !resolve(process.env.RUNNER_TEMP ?? "").toLowerCase().startsWith("d:\\")) {
  throw new Error("Owned P51-A17 synthetic identities and non-C RUNNER_TEMP child required");
}

const profile = await mkdtemp(join(tempRoot, "plm-p51-a17-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1100",
    "--ignore-certificate-errors", "about:blank"], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
let socket, serial = 0;
const pending = new Map(), requests = new Map(), responses = [], failures = [], errors = [];
function send(method, params = {}) {
  const id = ++serial; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, { resolve: resolveCall, reject: rejectCall }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Edge exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 300; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(-1800)})"))}; API=${JSON.stringify(responses.slice(-12).map(({method,path,status})=>({method,path,status})))}; failures=${JSON.stringify(failures.slice(-12))}; fetch=${JSON.stringify(await evaluate("window.__plmA17Fetch ?? []"))}`);
}
async function click(label) {
  if (!await evaluate(`(()=>{const e=[...document.querySelectorAll('button,a')].find(x=>x.textContent.trim()===${JSON.stringify(label)});if(!e||e.disabled)return false;e.click();return true})()`)) throw new Error(`Missing action: ${label}`);
}
async function fill(selector, value) {
  if (!await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;const s=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value')?.set;s?s.call(e,${JSON.stringify(value)}):e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`)) throw new Error(`Missing field: ${selector}`);
}
async function login(name) {
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.querySelector('#login-username')", "login form");
  await fill("#login-username", name); await fill("#login-password", password); await click("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", `login ${name}`);
}
async function route(path) {
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(path)});dispatchEvent(new PopStateEvent('popstate'))})()`);
}
async function check(selector) {
  if (!await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;e.checked=true;e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`)) throw new Error(`Missing checkbox: ${selector}`);
}
try {
  for (let n = 0; n < 100; n += 1) {
    try { const pages = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = pages.find(item => item.type === "page"); if (page) { socket = new WebSocket(page.webSocketDebuggerUrl); break; } }
    catch { /* Edge starts. */ }
    await pause(100);
  }
  if (!socket) throw new Error("Edge CDP unavailable");
  await new Promise((ok, bad) => { socket.addEventListener("open", ok, { once: true }); socket.addEventListener("error", bad, { once: true }); });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text ?? "browser exception");
    if (event.method === "Network.requestWillBeSent" && event.params.request.url.includes("/api/")) {
      const parsed = new URL(event.params.request.url);
      const safePath = parsed.pathname.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, ":id");
      requests.set(event.params.requestId, { method: event.params.request.method, path: safePath, url: event.params.request.url });
    }
    if (event.method === "Network.responseReceived" && requests.has(event.params.requestId)) {
      const request = requests.get(event.params.requestId);
      responses.push({ ...request, status: event.params.response.status });
    }
    if (event.method === "Network.loadingFailed" && requests.has(event.params.requestId)) {
      const request = requests.get(event.params.requestId);
      failures.push({ method: request.method, path: request.path, error: event.params.errorText,
        blockedReason: event.params.blockedReason ?? null, canceled: event.params.canceled ?? false });
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id); event.error ? task.reject(new Error(event.error.message)) : task.resolve(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await login(manager);
  await evaluate("(()=>{const original=window.fetch.bind(window);window.__plmA17Fetch=[];window.fetch=(input,init={})=>{const raw=typeof input===\"string\"?input:input.url;const url=new URL(raw,location.href);const path=url.pathname;if(!path.includes(\"/plans/\")||!path.includes(\"/versions/\"))return original(input,init);const item={method:init.method??\"GET\",path:path.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g,\":id\")};window.__plmA17Fetch.push({...item,phase:\"called\"});return original(input,init).then(response=>{window.__plmA17Fetch.push({...item,phase:\"response\",status:response.status});return response;},error=>{window.__plmA17Fetch.push({...item,phase:\"rejected\",error:String(error).slice(0,160)});throw error;});}})()");
  await route(`/projects/${project}/plans/new`);
  await waitFor("document.querySelector('#plan-name')", "plan create page");
  await fill("#plan-name", "P51-A17 Packaged Synthetic Plan"); await click("创建计划");
  await waitFor("document.body?.innerText?.includes('实施计划详情')&&document.body.innerText.includes('P51-A17 Packaged Synthetic Plan')", "plan created");
  const plan = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(plan) || !responses.some(x => x.status === 201 && x.url.includes(`/projects/${project}/plans`))) throw new Error("Plan identity creation HTTP evidence missing");
  await route(`/projects/${project}/plans/${plan}/versions/new`);
  await waitFor("document.querySelector('input[name=\"approved-solution\"]')", "approved Outline candidate");
  await check('input[name="approved-solution"]');
  await fill("#task-name-0", "合成实施任务一"); await fill("#task-acceptance-0", "任务一验收条件满足"); await check('input[type="checkbox"]');
  await click("增加WBS任务"); await fill("#task-name-1", "合成实施任务二"); await fill("#task-code-1", "TASK-002"); await fill("#task-acceptance-1", "任务二验收条件满足");
  if (await evaluate("document.querySelectorAll('input[type=checkbox]').length") < 2) throw new Error("Approved Requirement is not available");
  await evaluate("(()=>{const e=document.querySelectorAll('input[type=checkbox]')[1];e.checked=true;e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  await click("预览完整草稿"); await waitFor("document.body?.innerText?.includes('创建前预览')", "draft preview");
  await click("确认创建草稿版本"); await waitFor("document.body?.innerText?.includes('草稿版本已创建：')", "PlanVersion create receipt");
  await waitFor('document.body?.innerText?.includes("草稿版本已创建：") && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(location.pathname.split("/").at(-1) ?? "")', "PlanVersion fixed-readback detail route");
  const version = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(version)) throw new Error("Created PlanVersion identity missing");
  await click("查看固定版本"); await waitFor("document.body?.innerText?.includes('计划固定版本快照')", "fixed read");
  if (!responses.some(x => x.status === 201 && x.url.includes(`/plans/${plan}/versions`)) || !responses.some(x => x.status === 200 && x.url.includes(`/plans/${plan}/versions/${version}`))) throw new Error("PlanVersion Create/GET HTTP evidence missing");
  await click("核查此固定版本"); await waitFor("document.querySelector('button')?.textContent.includes('执行Validate')", "Validate page"); await click("执行Validate");
  await waitFor("document.body?.innerText?.includes('验证通过')||document.body?.innerText?.includes('发现阻断问题')", "validation result");
  if (await evaluate("document.body?.innerText?.includes('发现阻断问题')") || await evaluate("(()=>{const m=(document.body?.innerText??'').match(/未覆盖需求\\s*(\\d+)/);return m?Number(m[1]):null})()") !== 0) throw new Error("PlanVersion Validate not PASS / uncovered count not zero");
  await click("返回固定版本"); await waitFor("document.body?.innerText?.includes('提交此计划版本评审')", "review action"); await click("提交此计划版本评审");
  await waitFor("document.body?.innerText?.includes('读取项目评审人')", "review submission page"); await click("读取项目评审人"); await waitFor("document.querySelector('input[type=checkbox]')", "eligible reviewer");
  await check('input[type="checkbox"]');
  await evaluate("(()=>{const e=[...document.querySelectorAll('input[type=checkbox]')].find(x=>x.closest('label')?.textContent.includes('确认提交'));if(!e)throw new Error('missing submit confirmation');e.checked=true;e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  await click("确认提交正式评审"); await waitFor("document.body?.innerText?.includes('已进入正式评审')", "atomic review receipt");
  const reviewPath = await evaluate("location.pathname"); await send("Page.navigate", { url: `${origin}/login` }); await login(reviewer); await route(reviewPath);
  await waitFor("document.body?.innerText?.includes('计划版本评审')||document.body?.innerText?.includes('评审意见')", "read-only reviewer view");
  if (errors.length) throw new Error(`Browser exceptions: ${JSON.stringify(errors)}`);
  console.log(`P51_A17_PACKAGED_PLANVERSION_EDGE_PASS: plan=${plan}; version=${version}; HTTPS Edge Create/Get/Validate/SubmitReview/Review read; API=${responses.length}`);
} finally {
  try { socket?.close(); } catch { /* Owned Edge process is terminated below. */ }
  edge.kill(); await pause(500);
  if (!resolve(profile).startsWith(resolve(tempRoot) + sep)) throw new Error("Unsafe Edge profile cleanup scope");
  await rm(profile, { recursive: true, force: true, maxRetries: 15, retryDelay: 200 });
}
