/** Disposable packaged Windows Edge proof of the actual two-item editor. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, baseline] = process.argv.slice(2);
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "") || !/^[0-9a-f-]{36}$/.test(baseline ?? "")) {
  throw new Error("synthetic packaged origin and baseline required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-cap-multi-pkg-edge-"));
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
    } catch { /* Edge is starting. */ }
    await pause(100);
  }
  throw new Error("packaged Edge target unavailable");
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
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch { /* Navigation can replace the execution context briefly. */ }
    await pause(100);
  }
  throw new Error(`timeout ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,3000)})"))}`);
}
async function setInput(selector, value) {
  const found = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value').set;setter.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()`);
  if (!found) throw new Error(`missing input: ${selector}`);
}
async function clickButton(text) {
  const found = await evaluate(`(() => {const e=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()===${JSON.stringify(text)});if(!e)return false;e.click();return true;})()`);
  if (!found) throw new Error(`missing button: ${text}`);
}
async function selectDocument(title) {
  const found = await evaluate(`(() => {const li=[...document.querySelectorAll('li')].find(e=>e.textContent.includes(${JSON.stringify(title)})&&[...e.querySelectorAll('button')].some(b=>b.textContent.trim()==='选择版本'));const button=li&&[...li.querySelectorAll('button')].find(b=>b.textContent.trim()==='选择版本');if(!button)return false;button.click();return true;})()`);
  if (!found) throw new Error(`document not offered: ${title}`);
  await waitFor("[...document.querySelectorAll('button')].some(e=>e.textContent.trim()==='选用此固定版本')", "fixed version choice");
  await clickButton("选用此固定版本");
  await waitFor(`document.body.innerText.includes(${JSON.stringify(title + " · 第 1 版")})`, "chosen fixed source");
}
async function selectEvidence(label) {
  await waitFor(`[...document.querySelectorAll('label')].some(x=>x.textContent.includes(${JSON.stringify(label)})&&x.querySelector('input[type=checkbox]'))`, "eligible evidence choice");
  const found = await evaluate(`(() => {const e=[...document.querySelectorAll('label')].find(x=>x.textContent.includes(${JSON.stringify(label)})&&x.querySelector('input[type=checkbox]'));if(!e)return false;e.querySelector('input').click();return true;})()`);
  if (!found) throw new Error(`eligible evidence not offered: ${label}`);
}
async function fill(code, suffix, state) {
  for (const [selector, value] of Object.entries({
    "#cap-code": code, "#cap-domain": "PLM", "#cap-module": "Core",
    "#cap-feature": suffix, "#cap-name": `${suffix} packaged capability`,
    "#cap-description": `${suffix} synthetic fixed source`, "#cap-boundary": "GLOBAL only",
    "#cap-state": state,
  })) await setInput(selector, value);
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
  await waitFor("document.querySelector('#login-username')", "admin login form");
  await setInput("#login-username", "Synthetic Packaged User");
  await setInput("#login-password", "synthetic-packaged-login-password");
  await evaluate("document.querySelector('form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "admin login");
  const route = `/admin/capability-baselines/${baseline}/versions/new`;
  await evaluate(`history.pushState({},'',${JSON.stringify(route)});dispatchEvent(new PopStateEvent('popstate'))`);
  await waitFor("document.querySelector('#cap-code')&&document.body.innerText.includes('Synthetic Multi Baseline')", "version editor");
  await selectDocument("Synthetic Capability Source");
  await selectEvidence("Synthetic Whole Document Evidence");
  await fill("cap.multi.one", "First", "AVAILABLE");
  await clickButton("加入条目清单");
  await waitFor("document.body.innerText.includes('CAP.MULTI.ONE')&&document.querySelector('#cap-code').value===''", "first staged item");
  await selectDocument("Synthetic Multi Source Two");
  await selectEvidence("Synthetic Multi Evidence Two");
  await fill("cap.multi.two", "Second", "DEPRECATED");
  const before = await evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='创建 DRAFT 版本')?.disabled");
  if (before !== true) throw new Error("unstaged second item was not blocked");
  await clickButton("加入条目清单");
  await waitFor("document.body.innerText.includes('CAP.MULTI.TWO')&&document.querySelector('[aria-label=\"已加入能力条目\"]')?.querySelectorAll('li').length===2", "second staged item");
  await evaluate("document.querySelector('form input[type=checkbox]').click()");
  const enabled = await evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='创建 DRAFT 版本')?.disabled===false");
  if (!enabled) throw new Error("batch create remained disabled after attestation");
  await clickButton("创建 DRAFT 版本");
  await waitFor(`location.pathname===${JSON.stringify(`/capability-baselines/${baseline}`)}&&document.body.innerText.includes('Synthetic Multi Baseline')`, "created DRAFT navigation");
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  const failures = observations.filter(item => item.exception || item.status >= 400
    && !(item.url === "/api/v1/auth/session" && item.status === 401));
  const created = observations.some(item => item.url === `/api/v1/global/capability-baselines/${baseline}/versions`
    && item.status === 201);
  if (alerts.length || failures.length || !created) {
    throw new Error(`packaged editor mismatch: ${JSON.stringify({ alerts, failures, observations })}`);
  }
  console.log("CAP_02_P03_A03_PACKAGED_MULTI_ITEM_EDGE_PASS: two distinct sources and DEPRECATED");
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
