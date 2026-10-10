/** Owned headless Edge proof: lost CREATE response, reload, original-key recovery, reads. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, password] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "") || !uuid.test(project ?? "")
  || !uuid.test(otherProject ?? "") || project === otherProject
  || password !== "Synthetic-Outline-Browser-Only-2026") throw new Error("owned synthetic inputs required");

const profile = await mkdtemp(join(tmpdir(), "plm-outline-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1000", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = targets.find(target => target.type === "page");
      if (page) return page;
    } catch { /* Browser not listening yet. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket; let serial = 0; let failedOnce = false; let createKey = "";
const pending = new Map(); const responses = []; const errors = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 180; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,1600),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-10))}; errors=${JSON.stringify(errors.slice(-5))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});
    if(!item||item.disabled)return false;item.click();return true})()`)) {
    throw new Error(`Missing or disabled action ${label}`);
  }
}
async function login(username) {
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(()=>{const username=document.querySelector('#login-username');
    const password=document.querySelector('#login-password');
    username.value=${JSON.stringify(username)};username.dispatchEvent(new Event('input',{bubbles:true}));
    password.value=${JSON.stringify(password)};password.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "login success");
}
async function openCreate() {
  await clickText("我的项目");
  await waitFor("document.body?.innerText?.includes('Reference Project')", "project list");
  await clickText("Reference Project");
  await waitFor("document.body?.innerText?.includes('查看方案目录')", "project detail");
  await clickText("查看方案目录");
  await waitFor("document.body?.innerText?.includes('创建方案目录')", "outline list");
  await clickText("创建方案目录");
  await waitFor("document.querySelector('#outline-name')", "outline create");
}

try {
  const page = await findPage();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text);
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (event.method === "Network.requestWillBeSent" && event.params.request.method === "POST"
      && event.params.request.url.endsWith(`/api/v1/projects/${project}/solution-outlines`)) {
      const key = event.params.request.headers["Idempotency-Key"] ?? event.params.request.headers["idempotency-key"];
      if (createKey && createKey !== key) errors.push("Outline retry changed idempotency key");
      createKey = key;
    }
    if (event.method === "Fetch.requestPaused") {
      const { requestId, request, responseStatusCode } = event.params;
      const create = request.method === "POST"
        && request.url.endsWith(`/api/v1/projects/${project}/solution-outlines`);
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
  await send("Page.navigate", { url: `${origin}/login` });
  await login("Browser Outline Manager");
  await openCreate();
  await send("Fetch.enable", { patterns: [{ urlPattern: `*${project}/solution-outlines`, requestStage: "Response" }] });
  await evaluate(`(()=>{const item=document.querySelector('#outline-name');item.value='Browser Outline';
    item.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await clickText("创建目录");
  await waitFor("document.body?.innerText?.includes('创建结果无法确认')", "lost 201 recovery state");
  if (!failedOnce || !createKey || !await evaluate("sessionStorage.length === 1")) {
    throw new Error("First 201 was not lost with its original key retained");
  }
  await send("Page.reload", { ignoreCache: true });
  await send("Page.navigate", { url: `${origin}/login` });
  await login("Browser Outline Manager");
  await openCreate();
  if (!await evaluate("document.querySelector('#outline-name')?.disabled")) {
    throw new Error("Recovered input was not locked");
  }
  await evaluate(`(()=>{const item=document.querySelector('input[type=checkbox]');
    item.checked=true;item.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await clickText("按原操作号重试");
  await waitFor(`location.pathname.startsWith('/projects/${project}/solution-outlines/')
    && !location.pathname.endsWith('/new') && document.body?.innerText?.includes('Browser Outline')`, "created detail");
  const createdId = (await evaluate("location.pathname.split('/').at(-1)"));
  if (!uuid.test(createdId)) throw new Error("Invalid created outline ID");
  await waitFor("document.body?.innerText?.includes('尚无已审批版本')", "unapproved detail");
  await clickText("返回方案目录");
  await waitFor("document.body?.innerText?.includes('Browser Outline')", "created list");
  if (!await evaluate(`Boolean(document.querySelector('a[href="/projects/${project}/solution-outlines/${createdId}"]'))`)) {
    throw new Error("Created outline absent from list");
  }
  if (await evaluate("sessionStorage.length !== 0")) throw new Error("Original key not cleared on confirmed 201");
  await clickText("账户与登录");
  await login("Browser Outline Customer");
  await clickText("我的项目");
  await waitFor("document.body?.innerText?.includes('Reference Project')", "customer project list");
  await clickText("Reference Project");
  await waitFor("document.body?.innerText?.includes('查看方案目录')", "customer project detail");
  await clickText("查看方案目录");
  await waitFor("document.body?.innerText?.includes('Browser Outline')", "customer outline list");
  if (await evaluate(`Boolean(document.querySelector('a[href="/projects/${project}/solution-outlines/new"]'))`)) {
    throw new Error("Customer was shown Outline create entry");
  }
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log("OUTLINE_EDGE PASS: lost201/reload/same-key replay, detail/list, customer create hidden");
} finally {
  try { socket?.close(); } catch { /* Best effort owned cleanup. */ }
  edge.kill();
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Unsafe owned profile cleanup path");
  if (edge.exitCode === null && edge.signalCode === null) {
    await Promise.race([new Promise(resolve => edge.once("exit", resolve)), pause(3000)]);
  }
  await pause(500);
  await rm(profile, { recursive: true, force: true, maxRetries: 15, retryDelay: 200 });
}
