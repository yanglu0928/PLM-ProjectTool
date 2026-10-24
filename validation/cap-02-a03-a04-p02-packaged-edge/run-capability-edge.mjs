/** Isolated Edge proof of GLOBAL source upload and baseline identity creation. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin] = process.argv.slice(2);
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "")) throw new Error("synthetic HTTPS origin required");
const profile = await mkdtemp(join(tmpdir(), "plm-cap-a03a04-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", "--remote-debugging-address=127.0.0.1", `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--ignore-certificate-errors", "--window-size=1440,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket; let nextId = 0;
const pending = new Map(); const observations = [];
async function target() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const entries = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = entries.find(entry => entry.type === "page" && entry.url.startsWith(origin));
      if (page) return page;
    } catch { /* Browser is starting. */ }
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
async function click(text) {
  const done = await evaluate(`(() => {const x=[...document.querySelectorAll('a,button')].find(e=>e.textContent.trim()===${JSON.stringify(text)});if(!x)return false;x.click();return true;})()`);
  if (!done) throw new Error(`missing UI action: ${text}`);
}
async function setInput(selector, value) {
  const done = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`);
  if (!done) throw new Error(`missing input: ${selector}`);
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
    if (message.method === "Network.loadingFailed") observations.push({ loadingFailed: message.params.errorText });
    if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await setInput("#login-username", "Synthetic Packaged User");
  await setInput("#login-password", "synthetic-packaged-login-password");
  await evaluate("document.querySelector('form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "admin login");
  await click("标准能力");
  await waitFor("document.body.innerText.includes('上传标准能力来源文档')", "baseline list");
  await click("上传标准能力来源文档");
  await waitFor("document.querySelector('#capability-document-file')", "GLOBAL upload form");
  await setInput("#capability-document-title", "Synthetic Capability Source");
  const selected = await evaluate(`(() => {const e=document.querySelector('#capability-document-file'),dt=new DataTransfer();dt.items.add(new File(['Synthetic GLOBAL standard capability source.\\n'],'synthetic-capability.txt',{type:'text/plain'}));e.files=dt.files;e.dispatchEvent(new Event('change',{bubbles:true}));return e.files.length===1;})()`);
  if (!selected) throw new Error("synthetic in-memory GLOBAL file selection failed");
  await evaluate("document.querySelector('.document-upload input[type=checkbox]').click()");
  await evaluate("document.querySelector('.document-upload form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('首次提交回执：文档')", "GLOBAL commit");
  await click("重新读取文档及固定版本状态");
  await waitFor("document.body.innerText.includes('已独立读取到全局文档')", "GLOBAL fixed version AVAILABLE");
  await click("返回标准能力基线");
  await waitFor("document.body.innerText.includes('从固定来源创建基线')", "baseline list return");
  await click("从固定来源创建基线");
  await waitFor("document.querySelector('#baseline-code')&&document.body.innerText.includes('Synthetic Capability Source')", "baseline source choices");
  await click("选择固定版本");
  await waitFor("document.body.innerText.includes('第 1 版')", "fixed version picker");
  await click("选用此版本");
  await setInput("#baseline-code", "CAP.SYNTHETIC.PKG");
  await setInput("#baseline-name", "Synthetic Package Baseline");
  await evaluate("document.querySelector('form button[type=submit]').click()");
  await waitFor("location.pathname.includes('/capability-baselines/')&&document.body.innerText.includes('Synthetic Package Baseline')", "baseline detail");
  const relevant = observations.filter(item => item.url?.includes("/api/v1/global/") || item.url?.includes("/api/v1/auth/"));
  const failures = relevant.filter(item => item.exception || item.loadingFailed || item.status >= 400);
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  if (failures.length || alerts.length || !relevant.some(item =>
    item.url === "/api/v1/global/capability-baselines" && item.status === 201)) {
    throw new Error(`browser capability flow mismatch: ${JSON.stringify({ failures, alerts, observations })}`);
  }
  console.log("CAP_02_A03_A04_P02_PACKAGED_EDGE_PASS");
  console.log(JSON.stringify({ status: "PASS", globalFixedVersion: true,
    baselineIdentityCreated: true, apiResponses: relevant.length }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
