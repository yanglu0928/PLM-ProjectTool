/** Packaged Solution Outline identity create/read proof using a synthetic project. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project] = process.argv.slice(2);
const managerName = process.env.PLM_SOLUTION_TEST_MANAGER;
const password = process.env.PLM_SOLUTION_TEST_PASSWORD;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^(https:\/\/localhost:\d{2,5}|http:\/\/127\.0\.0\.1:\d{2,5})$/.test(origin ?? "")
  || !uuid.test(project ?? "")
  || !managerName || typeof password !== "string" || password.length < 24) {
  throw new Error("Owned synthetic packaged Solution inputs required");
}

const profile = await mkdtemp(join(tmpdir(), "plm-p51-a06-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edgeArgs = ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1000"];
if (origin.startsWith("https://")) edgeArgs.push("--ignore-certificate-errors");
edgeArgs.push("about:blank");
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  edgeArgs,
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = targets.find(item => item.type === "page");
      if (page) return page;
    } catch { /* Owned Edge is starting. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket, serial = 0;
const pending = new Map(), responses = [], errors = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, {
    resolve: resolveCall, reject: rejectCall,
  }));
}
async function evaluate(expression) {
  const answer = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (answer.exceptionDetails) throw new Error(`Browser exception: ${answer.exceptionDetails.text}`);
  return answer.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 300; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  const state = await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,2400),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})");
  throw new Error(`Timed out ${label}: ${JSON.stringify(state)}; responses=${JSON.stringify(responses.slice(-20))}; errors=${JSON.stringify(errors.slice(-5))}`);
}
async function clickText(label) {
  const clicked = await evaluate(`(()=>{const node=[...document.querySelectorAll('a,button')].find(x=>x.textContent.trim()===${JSON.stringify(label)});if(!node||node.disabled)return false;node.click();return true})()`);
  if (!clicked) throw new Error(`Missing or disabled action ${label}`);
}
async function setValue(selector, value) {
  await evaluate(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});if(!input)throw new Error('Missing input');input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}))})()`);
}
async function login(name) {
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", name);
  await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "account login");
}
async function route(path) {
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(path)});dispatchEvent(new PopStateEvent('popstate'))})()`);
}

let outline;
try {
  const page = await findPage(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((ok, bad) => {
    socket.addEventListener("open", ok, { once: true });
    socket.addEventListener("error", bad, { once: true });
  });
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
  const edgeVersion = await send("Browser.getVersion");
  await login(managerName);

  await route(`/projects/${project}/solution-outlines/new`);
  await waitFor("document.querySelector('#outline-name')", "Outline identity create page");
  await setValue("#outline-name", "P51-A06 Synthetic Solution Outline");
  await clickText("创建目录");
  await waitFor("document.body?.innerText?.includes('方案目录详情')&&document.body.innerText.includes('P51-A06 Synthetic Solution Outline')",
    "created Outline identity read");
  outline = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(outline ?? "")) throw new Error("Created Outline identity link missing");
  if (!responses.some(item => item.url.includes(`/api/v1/projects/${project}/solution-outlines`)
    && item.status === 201)) throw new Error("Outline create HTTP 201 missing");
  if (!responses.some(item => item.url.includes(`/api/v1/projects/${project}/solution-outlines/${outline}`)
    && item.status === 200)) throw new Error("Outline read HTTP 200 missing");
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  if (typeof screenshot.data !== "string" || screenshot.data.length < 1000 || errors.length) {
    throw new Error(`Edge render/exception failure: ${JSON.stringify(errors)}`);
  }
  console.log(`P51_A06_RESULT ${JSON.stringify({ outline, screenshot_bytes: Math.floor(screenshot.data.length * 3 / 4) })}`);
  console.log(`P51_A06_PACKAGED_SOLUTION_EDGE_PASS: ${edgeVersion.product}; Solution Outline identity create/read`);
} finally {
  try { socket?.close(); } catch { /* Owned Edge shuts down below. */ }
  edge.kill(); await new Promise(done => edge.once("exit", done));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Edge profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
