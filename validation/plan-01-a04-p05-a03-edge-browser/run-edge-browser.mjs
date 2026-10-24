/** Owned headless Edge proof of Plan creation, recovery, pagination and isolation. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const manager = process.env.PLM_BROWSER_MANAGER_NAME;
const customer = process.env.PLM_BROWSER_CUSTOMER_NAME;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || !uuid.test(project ?? "") || !uuid.test(otherProject ?? "")
  || project === otherProject || typeof password !== "string" || password.length < 24
  || manager !== "Browser Plan Manager" || customer !== "Browser Plan Customer") {
  throw new Error("Owned synthetic browser inputs required");
}

const profile = await mkdtemp(join(tmpdir(), "plm-plan-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1000", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = targets.find(target => target.type === "page");
      if (page) return page;
    } catch { /* Owned browser is starting. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket; let serial = 0; let failedOnce = false; let createKey = "";
const pending = new Map(); const responses = []; const errors = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, {
    resolve: resolveCall, reject: rejectCall,
  }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 240; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,2000),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-15))}; errors=${JSON.stringify(errors.slice(-5))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});
    if(!item||item.disabled)return false;item.click();return true})()`)) {
    throw new Error(`Missing or disabled action ${label}`);
  }
}
async function setValue(selector, value) {
  await evaluate(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});
    if(!input)throw new Error('Missing input');input.value=${JSON.stringify(value)};
    input.dispatchEvent(new Event('input',{bubbles:true}))})()`);
}
async function login(username) {
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", username);
  await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "login success");
}
async function openCreate() {
  await clickText("我的项目");
  await waitFor("document.body?.innerText?.includes('Reference Project')", "project list");
  await clickText("Reference Project");
  await waitFor("document.body?.innerText?.includes('查看实施计划')", "project detail");
  await clickText("查看实施计划");
  await waitFor("document.body?.innerText?.includes('创建实施计划')", "Plan list");
  await clickText("创建实施计划");
  await waitFor("document.querySelector('#plan-name')", "Plan create");
}
function route(path) {
  return evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(path)});
    dispatchEvent(new PopStateEvent('popstate'))})()`);
}

try {
  const page = await findPage();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolveCall, rejectCall) => {
    socket.addEventListener("open", resolveCall, { once: true });
    socket.addEventListener("error", rejectCall, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text);
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (event.method === "Network.requestWillBeSent" && event.params.request.method === "POST"
      && event.params.request.url.endsWith(`/api/v1/projects/${project}/plans`)) {
      const key = event.params.request.headers["Idempotency-Key"] ?? event.params.request.headers["idempotency-key"];
      if (createKey && createKey !== key) errors.push("Plan retry changed idempotency key");
      createKey = key;
    }
    if (event.method === "Fetch.requestPaused") {
      const { requestId, request, responseStatusCode } = event.params;
      const create = request.method === "POST"
        && request.url.endsWith(`/api/v1/projects/${project}/plans`);
      if (create && !failedOnce && responseStatusCode === 201) {
        failedOnce = true;
        void (async () => {
          try {
            await send("Fetch.failRequest", { requestId, errorReason: "Failed" });
            await send("Fetch.disable");
          } catch (error) { errors.push(String(error)); }
        })();
      } else {
        void send("Fetch.continueResponse", { requestId }).catch(error => errors.push(String(error)));
      }
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolve(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  const edgeVersion = await send("Browser.getVersion");
  await send("Page.navigate", { url: `${origin}/login` });
  await login(manager);
  await openCreate();
  await send("Fetch.enable", { patterns: [{ urlPattern: `*${project}/plans`, requestStage: "Response" }] });
  await setValue("#plan-name", "Browser Plan");
  await clickText("创建计划");
  await waitFor("document.body?.innerText?.includes('创建结果无法确认')", "lost 201 recovery state");
  if (!failedOnce || !createKey || !await evaluate("sessionStorage.length === 1")) {
    throw new Error("First 201 was not lost with its original key retained");
  }
  await send("Page.reload", { ignoreCache: true });
  await send("Page.navigate", { url: `${origin}/login` });
  await login(manager);
  await openCreate();
  if (!await evaluate("document.querySelector('#plan-name')?.disabled")) {
    throw new Error("Recovered Plan input was not locked");
  }
  await evaluate(`(()=>{const item=document.querySelector('input[type=checkbox]');
    item.checked=true;item.dispatchEvent(new Event('change',{bubbles:true}))})()`);
  await clickText("按原操作号重试");
  await waitFor(`location.pathname.startsWith('/projects/${project}/plans/')
    && !location.pathname.endsWith('/new') && document.body?.innerText?.includes('Browser Plan')`, "created detail");
  const createdId = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(createdId)) throw new Error("Invalid created Plan ID");
  await waitFor("document.body?.innerText?.includes('尚无已审批计划版本')", "unapproved detail");
  await clickText("返回实施计划");
  await waitFor("document.body?.innerText?.includes('Browser Plan')", "created list");
  if (!await evaluate(`Boolean(document.querySelector('a[href="/projects/${project}/plans/${createdId}"]'))`)) {
    throw new Error("Created Plan absent from list");
  }
  await waitFor("document.body?.innerText?.includes('加载更多计划')", "second page available");
  await clickText("加载更多计划");
  await waitFor("document.querySelectorAll('ol[aria-label=\"项目实施计划\"] li').length===51", "all 51 Plan identities");
  if (await evaluate("sessionStorage.length !== 0")) throw new Error("Original key not cleared on confirmed 201");
  if (responses.filter(item => item.url.includes(`/api/v1/projects/${project}/plans?page_size=50`)
    && item.status === 200).length < 2) throw new Error("No real Plan LIST second page");
  await clickText("账户与登录");
  await login(customer);
  await clickText("我的项目");
  await waitFor("document.body?.innerText?.includes('Reference Project')", "customer project list");
  await clickText("Reference Project");
  await waitFor("document.body?.innerText?.includes('查看实施计划')", "customer project detail");
  await clickText("查看实施计划");
  await waitFor("document.body?.innerText?.includes('Browser Plan')", "customer Plan list");
  if (await evaluate(`Boolean(document.querySelector('a[href="/projects/${project}/plans/new"]'))`)) {
    throw new Error("Customer was shown Plan create entry");
  }
  await route(`/projects/${otherProject}/plans`);
  await waitFor("document.body?.innerText?.includes('无权查看此项目')", "cross-project clear");
  if (await evaluate("document.body?.innerText?.includes('Browser Plan')")) {
    throw new Error("Cross-project page retained Plan content");
  }
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  if (typeof screenshot.data !== "string" || screenshot.data.length < 1000 || errors.length) {
    throw new Error(`Edge render/exception failure: ${JSON.stringify(errors)}`);
  }
  console.log(`PLAN_EDGE PASS: ${edgeVersion.product}; lost201/reload/same-key replay, 51-item pagination, customer read-only, cross-project clear, PNG bytes=${Math.floor(screenshot.data.length * 3 / 4)}`);
} finally {
  try { socket?.close(); } catch { /* Owned cleanup. */ }
  edge.kill();
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) {
    throw new Error("Unsafe owned Edge profile cleanup path");
  }
  if (edge.exitCode === null && edge.signalCode === null) {
    await Promise.race([new Promise(done => edge.once("exit", done)), pause(3000)]);
  }
  await pause(500);
  await rm(profile, { recursive: true, force: true, maxRetries: 15, retryDelay: 200 });
}
