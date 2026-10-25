/** Disposable Edge proof for packaged PROJECT Survey definition Create. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, project, observer] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "")
  || [project, observer].some(value => !uuid.test(value ?? ""))) {
  throw new Error("synthetic HTTPS origin and canonical IDs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-survey-create-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", "--remote-debugging-address=127.0.0.1", `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--ignore-certificate-errors", "--window-size=1500,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket; let nextId = 0; const pending = new Map(); const observations = [];
let createRequest = null; let createResponseId = null;
const createPath = `/api/v1/projects/${project}/surveys`;
const surveyName = "Synthetic Face-to-Face Survey Definition";
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
    catch { /* Navigation briefly replaces execution context. */ }
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
      const path = new URL(message.params.response.url).pathname;
      observations.push({ url: path, status: message.params.response.status });
      if (path === createPath && message.params.response.status === 201 && !createResponseId) {
        createResponseId = message.params.requestId;
      }
    }
    if (message.method === "Network.loadingFailed") observations.push({ loadingFailed: message.params.errorText });
    if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (message.method === "Network.requestWillBeSent" && message.params.request.method === "POST"
      && new URL(message.params.request.url).pathname === createPath && !createRequest) {
      createRequest = message.params.request;
    }
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", "Synthetic Handover Observer");
  await setValue("#login-password", "synthetic-packaged-login-password");
  await evaluate("document.querySelector('form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  const listRoute = `/projects/${project}/surveys`;
  await evaluate(`history.pushState({},'',${JSON.stringify(listRoute)});dispatchEvent(new PopStateEvent('popstate'))`);
  await waitFor("document.querySelector('#survey-create-title')&&document.querySelector('#survey-create-name')", "survey create form");
  const warning = await evaluate("document.body.innerText");
  if (!warning.includes("面对面访谈") || !warning.includes("不会自动确认客户事实")) {
    throw new Error("survey create boundary warning missing");
  }
  await setValue("#survey-create-name", surveyName);
  await click("创建调研定义");
  await waitFor(`location.pathname.startsWith(${JSON.stringify(listRoute + "/")})&&document.querySelector('#survey-detail-title')`, "created survey detail");
  if (!createRequest || !createResponseId || !header(createRequest, "Idempotency-Key")
    || !header(createRequest, "X-CSRF-Token") || !createRequest.postData) {
    throw new Error("browser Create missing request, key, CSRF or body");
  }
  const body = await send("Network.getResponseBody", { requestId: createResponseId });
  if (body.base64Encoded) throw new Error("unexpected encoded Survey response");
  const created = JSON.parse(body.body).data;
  if (!uuid.test(created?.survey_id ?? "") || created.project_id !== project
    || created.name !== surveyName) {
    throw new Error(`Create response mismatch: ${JSON.stringify(created)}`);
  }
  const detailRoute = `${listRoute}/${created.survey_id}`;
  if (await evaluate("location.pathname") !== detailRoute) throw new Error("detail route differs from receipt");
  const replay = await evaluate(`(async () => {const r=await fetch(${JSON.stringify(createPath)},{method:'POST',credentials:'same-origin',headers:${JSON.stringify({
    "X-CSRF-Token": header(createRequest, "X-CSRF-Token"),
    "Idempotency-Key": header(createRequest, "Idempotency-Key"),
    "Content-Type": "application/json",
  })},body:${JSON.stringify(createRequest.postData)}});const j=await r.json();return {status:r.status,data:j.data,code:j.error?.code};})()`);
  if (replay.status !== 201 || replay.data?.survey_id !== created.survey_id) {
    throw new Error(`same-key replay failed: ${JSON.stringify(replay)}`);
  }
  const failures = observations.filter(item => item.exception || item.loadingFailed
    || item.status >= 400 && !(item.url === "/api/v1/auth/session" && item.status === 401));
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  if (failures.length || alerts.length) throw new Error(`browser failures: ${JSON.stringify({ failures, alerts })}`);
  console.log(JSON.stringify({ status: "SUR_07_A03_PACKAGED_EDGE_PASS", survey_id: created.survey_id,
    project_id: project, name: surveyName, actor_id: observer }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
