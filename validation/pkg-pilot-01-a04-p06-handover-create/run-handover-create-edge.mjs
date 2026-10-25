/** Real packaged UI, disposable synthetic authority and in-memory text source. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin] = process.argv.slice(2);
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "")) throw new Error("synthetic HTTPS origin required");
const profile = await mkdtemp(join(tmpdir(), "plm-pkg-a04p06-edge-"));
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
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await click("我的项目");
  await waitFor("document.body.innerText.includes('Synthetic packaged Workflow HTTPS')", "own project");
  await click("Synthetic packaged Workflow HTTPS");
  await waitFor("document.querySelector('#project-title')&&document.body.innerText.includes('查看项目文档历史')", "loaded project detail");
  await click("查看项目文档历史");
  await waitFor("document.querySelector('#document-list-title')", "document list");
  await click("上传新文档");
  await waitFor("document.querySelector('#upload-title-input')", "upload form");
  await setInput("#upload-title-input", "Synthetic Handover Source");
  const selected = await evaluate(`(() => {const e=document.querySelector('#upload-file'),dt=new DataTransfer();dt.items.add(new File(['Synthetic fixed-version handover source.\\n'],'synthetic-handover.txt',{type:'text/plain'}));e.files=dt.files;e.dispatchEvent(new Event('change',{bubbles:true}));return e.files.length===1;})()`);
  if (!selected) throw new Error("synthetic in-memory file selection failed");
  await evaluate("document.querySelector('.document-upload input[type=checkbox]').click()");
  await evaluate("document.querySelector('.document-upload form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('首次提交回执：文档')", "fixed document commit");
  await click("返回项目文档历史");
  await waitFor("document.querySelector('#document-list-title')&&document.body.innerText.includes('Synthetic Handover Source')", "committed document list");
  await click("返回项目详情");
  await waitFor("document.querySelector('#project-title')&&document.body.innerText.includes('查看项目交接分析与待确认事项')", "loaded project detail return");
  await click("查看项目交接分析与待确认事项");
  await waitFor("document.querySelector('#handover-list-title')", "handover list");
  await click("创建交接分析");
  await waitFor("document.querySelector('#handover-create-title')&&document.body.innerText.includes('Synthetic Handover Source')", "handover source choices");
  await click("选择固定版本");
  await waitFor("document.body.innerText.includes('版本 1')", "fixed version picker");
  await click("选用此版本");
  await setInput("#handover-purpose", "Synthetic Handover Analysis");
  await evaluate("document.querySelector('.handover-create form button[type=submit]').click()");
  await waitFor("document.querySelector('#handover-detail-title')", "new handover detail");
  const failures = observations.filter(item => item.exception || item.loadingFailed || item.status >= 400);
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  if (failures.length || alerts.length || !observations.some(item =>
    item.url?.endsWith("/handover-analyses") && item.status === 201)) {
    throw new Error(`browser Handover create mismatch: ${JSON.stringify({ failures, alerts, observations })}`);
  }
  console.log("PKG_PILOT_01_A04_P06_HANDOVER_EDGE_PASS");
  console.log(JSON.stringify({ status: "PASS", fixedDocument: true, analysisCreated: true,
    apiResponses: observations.length }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
