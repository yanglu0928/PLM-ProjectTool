/** Disposable Edge proof for packaged Handover review and fixed version. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, project, analysis, version, review, round, customer] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "")
  || [project, analysis, version, review, round, customer].some(value => !uuid.test(value ?? ""))) {
  throw new Error("synthetic HTTPS origin and six canonical IDs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-hnd-review-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", "--remote-debugging-address=127.0.0.1", `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--ignore-certificate-errors", "--window-size=1500,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket; let nextId = 0; const pending = new Map(); const observations = [];
let decideRequest = null;
const decidePath = `/api/v1/projects/${project}/reviews/${review}/rounds/${round}:decide`;
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
    catch { /* Navigation briefly replaces the execution context. */ }
    await pause(100);
  }
  throw new Error(`timeout ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,3500)})"))}`);
}
async function click(text) {
  const done = await evaluate(`(() => {const x=[...document.querySelectorAll('a,button')].find(e=>e.textContent.trim()===${JSON.stringify(text)});if(!x)return false;x.click();return true;})()`);
  if (!done) throw new Error(`missing UI action: ${text}`);
}
async function setValue(selector, value) {
  const done = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`);
  if (!done) throw new Error(`missing input: ${selector}`);
}
function header(request, name) {
  return Object.entries(request?.headers ?? {}).find(([key]) => key.toLowerCase() === name.toLowerCase())?.[1];
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
    if (message.method === "Network.requestWillBeSent" && message.params.request.method === "POST") {
      const path = new URL(message.params.request.url).pathname;
      if (path === decidePath && !decideRequest) decideRequest = message.params.request;
    }
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", "Synthetic Handover Customer");
  await setValue("#login-password", "synthetic-packaged-login-password");
  await evaluate("document.querySelector('form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  const reviewRoute = `/projects/${project}/reviews/${review}`;
  await evaluate(`history.pushState({},'',${JSON.stringify(reviewRoute)});dispatchEvent(new PopStateEvent('popstate'))`);
  await waitFor(`document.querySelector('#review-title')&&document.body.innerText.includes('本轮固定交接版本 ID')&&document.body.innerText.includes(${JSON.stringify(version)})`, "Handover review");
  const fixedLink = await evaluate(`(() => {const a=[...document.querySelectorAll('a')].find(e=>e.textContent.trim()==='打开本轮固定交接版本');return a?.getAttribute('href')??null;})()`);
  if (fixedLink !== `/projects/${project}/handover/${analysis}?fixedVersionId=${version}`) {
    throw new Error(`fixed version link mismatch: ${fixedLink}`);
  }
  await click("打开本轮固定交接版本");
  await waitFor(`location.pathname===${JSON.stringify(`/projects/${project}/handover/${analysis}`)}&&location.search.includes(${JSON.stringify(version)})&&document.querySelectorAll('article.issue-card').length===2`, "fixed Handover version and issues");
  const fixedText = await evaluate("document.body.innerText");
  if (!fixedText.includes("固定版本 1")) throw new Error("fixed version label missing");
  await click("打开评审与人工决定");
  await waitFor(`location.pathname===${JSON.stringify(reviewRoute)}&&document.querySelector('#review-title')&&document.body.innerText.includes('批准本轮')`, "review decision");
  const checked = await evaluate("(() => {const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes('我已核对固定交接分析版本'));if(!label)return false;const input=label.querySelector('input[type=checkbox]');if(!input)return false;input.click();return input.checked;})()");
  if (!checked) throw new Error("review scope confirmation missing");
  await click("批准本轮");
  await waitFor("document.body.innerText.includes('决定已记录：批准')&&document.body.innerText.includes('状态：已批准')", "approved review");
  if (!decideRequest || !header(decideRequest, "Idempotency-Key") || !header(decideRequest, "X-CSRF-Token") || !decideRequest.postData) {
    throw new Error("original browser decision missing key, CSRF or body");
  }
  const replay = await evaluate(`(async () => {const r=await fetch(${JSON.stringify(decidePath)},{method:'POST',credentials:'same-origin',headers:${JSON.stringify({
    "X-CSRF-Token": header(decideRequest, "X-CSRF-Token"),
    "Idempotency-Key": header(decideRequest, "Idempotency-Key"),
    "Content-Type": "application/json",
  })},body:${JSON.stringify(decideRequest.postData)}});const j=await r.json();return {status:r.status,data:j.data,code:j.error?.code};})()`);
  if (replay.status !== 200 || replay.data?.state !== "APPROVED") {
    throw new Error(`same-key decision replay failed: ${JSON.stringify(replay)}`);
  }
  const failures = observations.filter(item => item.exception || item.loadingFailed
    || item.status >= 400 && !(item.url === "/api/v1/auth/session" && item.status === 401));
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  if (failures.length || alerts.length) throw new Error(`browser failures: ${JSON.stringify({ failures, alerts })}`);
  console.log(`HND_05_A05_P06_PACKAGED_EDGE_PASS: HND review, fixed version, approve, same-key replay ${review}`);
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
