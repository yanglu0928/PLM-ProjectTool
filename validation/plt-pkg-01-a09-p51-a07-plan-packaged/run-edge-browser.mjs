/** Packaged Plan identity create/read proof in a synthetic project. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, foreignProject] = process.argv.slice(2);
const username = process.env.PLM_PLAN_TEST_MANAGER;
const password = process.env.PLM_PLAN_TEST_PASSWORD;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^(https:\/\/localhost:\d{2,5}|http:\/\/127\.0\.0\.1:\d{2,5})$/.test(origin ?? "")
  || !uuid.test(project ?? "") || (foreignProject !== undefined && !uuid.test(foreignProject))
  || !username || typeof password !== "string" || password.length < 24) {
  throw new Error("Owned synthetic packaged Plan inputs required");
}

const profile = await mkdtemp(join(tmpdir(), "plm-p51-a07-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edgeArgs = ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1000"];
if (origin.startsWith("https://")) edgeArgs.push("--ignore-certificate-errors");
edgeArgs.push("about:blank");
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  edgeArgs, { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const pages = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = pages.find(item => item.type === "page"); if (page) return page;
    } catch { /* Owned Edge is starting. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket, serial = 0;
const pending = new Map(), responses = [], errors = [];
function send(method, params = {}) {
  const id = ++serial; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, { resolve: resolveCall, reject: rejectCall }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 300; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,2400)})"))}; responses=${JSON.stringify(responses.slice(-20))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const x=[...document.querySelectorAll('a,button')].find(e=>e.textContent.trim()===${JSON.stringify(label)});if(!x||x.disabled)return false;x.click();return true})()`)) {
    throw new Error(`Missing or disabled action ${label}`);
  }
}
async function setValue(selector, value) {
  await evaluate(`(()=>{const x=document.querySelector(${JSON.stringify(selector)});if(!x)throw new Error('Missing input');x.value=${JSON.stringify(value)};x.dispatchEvent(new Event('input',{bubbles:true}))})()`);
}
async function route(path) {
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(path)});dispatchEvent(new PopStateEvent('popstate'))})()`);
}
async function login() {
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", username); await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "account login");
}

let plan;
try {
  const page = await findPage(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((ok, bad) => { socket.addEventListener("open", ok, { once: true }); socket.addEventListener("error", bad, { once: true }); });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text);
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolve(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  const edgeVersion = await send("Browser.getVersion"); await login();
  await route(`/projects/${project}/plans/new`);
  await waitFor("document.querySelector('#plan-name')", "Plan identity create page");
  await setValue("#plan-name", "P51-A07 Synthetic Implementation Plan");
  await clickText("创建计划");
  await waitFor("document.body?.innerText?.includes('实施计划详情')&&document.body.innerText.includes('P51-A07 Synthetic Implementation Plan')",
    "created Plan identity read");
  plan = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(plan ?? "")) throw new Error("Created Plan identity path is invalid");
  if (!responses.some(item => item.url.includes(`/api/v1/projects/${project}/plans`) && item.status === 201)) {
    throw new Error("Plan create HTTP 201 missing");
  }
  if (!responses.some(item => item.url.includes(`/api/v1/projects/${project}/plans/${plan}`) && item.status === 200)) {
    throw new Error("Plan read HTTP 200 missing");
  }
  if (foreignProject !== undefined) {
    const deniedPath = `/api/v1/projects/${foreignProject}/plans/${plan}`;
    const denied = await evaluate(`fetch(${JSON.stringify(deniedPath)}, {credentials:'same-origin',headers:{Accept:'application/json'}}).then(async r=>({status:r.status,body:await r.text()}))`);
    if (denied.status !== 404 || denied.body.includes(plan)
      || denied.body.includes("P51-A07 Synthetic Implementation Plan")) {
      throw new Error(`Cross-project Plan read was not non-enumerating: ${JSON.stringify(denied)}`);
    }
    if (!responses.some(item => item.url.includes(`/api/v1/projects/${foreignProject}/plans/`) && item.status === 404)) {
      throw new Error("Cross-project Plan read HTTP 404 missing");
    }
    console.log("P51_A08_CROSS_PROJECT_PLAN_READ_404_PASS: target identity not disclosed");
  }
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  if (typeof screenshot.data !== "string" || screenshot.data.length < 1000 || errors.length) {
    throw new Error(`Edge render/exception failure: ${JSON.stringify(errors)}`);
  }
  console.log(`P51_A07_RESULT ${JSON.stringify({ plan, screenshot_bytes: Math.floor(screenshot.data.length * 3 / 4) })}`);
  console.log(`P51_A07_PACKAGED_PLAN_EDGE_PASS: ${edgeVersion.product}; Plan identity create/read only`);
} finally {
  try { socket?.close(); } catch { /* Owned Edge shuts down below. */ }
  edge.kill(); await new Promise(done => edge.once("exit", done));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Edge profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
