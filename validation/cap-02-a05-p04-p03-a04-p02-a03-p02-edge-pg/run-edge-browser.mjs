/** Real Edge UI over the isolated synthetic FastAPI/PG Review fixture. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, baseline, version, review] = process.argv.slice(2);
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin ?? "")) throw new Error("local synthetic origin required");
const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profile = await mkdtemp(join(tmpdir(), "plm-cap-fixed-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn(edgePath, ["--headless=new", "--remote-debugging-address=127.0.0.1",
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run",
  "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1200", `${origin}/login`],
{ stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket; let nextId = 0;
const pending = new Map(); const observations = [];
async function target() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const entries = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = entries.find(entry => entry.type === "page" && entry.url.startsWith(origin));
      if (page) return page;
    } catch { /* Edge is starting. */ }
    await pause(100);
  }
  throw new Error("isolated Edge target unavailable");
}
function send(method, params = {}) {
  const id = ++nextId; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await pause(100);
  }
  throw new Error(`timeout ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,3000)})"))}`);
}
async function setInput(selector, value) {
  const found = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value').set;setter.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`);
  if (!found) throw new Error(`missing input: ${selector}`);
}
try {
  const page = await target(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true }); });
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === "Network.responseReceived" && message.params.response.url.includes("/api/")) {
      observations.push({ url: new URL(message.params.response.url).pathname,
        status: message.params.response.status });
    }
    if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await setInput("#login-username", "Synthetic Assigned Reviewer");
  await setInput("#login-password", "synthetic-only");
  await evaluate("document.querySelector('form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "reviewer login");
  const route = `/capability-baselines/${baseline}/versions/${version}/reviews/${review}`;
  await evaluate(`history.pushState({},'',${JSON.stringify(route)});dispatchEvent(new PopStateEvent('popstate'))`);
  await waitFor("document.body.innerText.includes('HTTP Item 1')", "second fixed item");
  const initial = await evaluate(`(() => ({title:document.body.innerText.includes('标准能力正式内部评审'),
    first:document.body.innerText.includes('HTTP Item 0'),second:document.body.innerText.includes('HTTP Item 1'),
    disabled:[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='批准本轮版本')?.disabled}))()`);
  if (!initial.title || !initial.first || !initial.second || !initial.disabled) {
    throw new Error(`fixed content not gated: ${JSON.stringify(initial)}`);
  }
  await evaluate(`(() => {const e=document.querySelector('section[aria-label="标准能力固定版本评审"] input[type=checkbox]');if(!e)throw Error('scope confirmation missing');e.click();})()`);
  const enabled = await evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='批准本轮版本')?.disabled===false");
  if (!enabled) throw new Error("approval did not enable after full fixed content confirmation");
  await evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='批准本轮版本').click()");
  await waitFor("document.body.innerText.includes('你已完成本轮决定')", "review decision receipt");
  const failures = observations.filter(item => item.exception || item.status >= 400
    && !(item.url === "/api/v1/auth/session" && item.status === 401));
  const required = ["/api/v1/auth/login", `/api/v1/global/reviews/${review}`,
    `/api/v1/global/reviews/${review}/fixed-version`,
    `/api/v1/global/reviews/${review}/fixed-items`,
    `/api/v1/global/reviews/${review}/rounds/`];
  if (failures.length || required.some(path => !observations.some(item => item.url?.startsWith(path) && item.status < 400))) {
    throw new Error(`Edge/API mismatch: ${JSON.stringify({ failures, observations })}`);
  }
  console.log("CAP_02_A05_P04_P03_A04_P02_A03_P02_EDGE_PASS: fixed content, gated click, decision");
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
