/** Disposable Edge proof for packaged Handover validate -> submit-review UI. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, project, analysis, version, customer, sourceItem, outsider] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "")
  || [project, analysis, version, customer, sourceItem, outsider].some(value => !uuid.test(value ?? ""))) {
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
let validateRequest = null; let submitRequest = null; let loginResponseId = null;
const validatePath = `/api/v1/projects/${project}/handover-analyses/${analysis}/versions/${version}:validate`;
const submitPath = `/api/v1/projects/${project}/handover-analyses/${analysis}/versions/${version}:submit-review`;
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
async function replay(path, request, expectedStatus) {
  if (!header(request, "Idempotency-Key") || !header(request, "X-CSRF-Token")) {
    throw new Error(`original browser operation missing key or CSRF: ${path}`);
  }
  const result = await evaluate(`(async () => {const r=await fetch(${JSON.stringify(path)},{method:'POST',credentials:'same-origin',headers:${JSON.stringify({
    "X-CSRF-Token": header(request, "X-CSRF-Token"),
    "Idempotency-Key": header(request, "Idempotency-Key"),
    ...(request.postData ? { "Content-Type": "application/json" } : {}),
  })}${request.postData ? `,body:${JSON.stringify(request.postData)}` : ""}});return {status:r.status,data:(await r.json()).data};})()`);
  if (result.status !== expectedStatus) throw new Error(`same-key replay failed: ${JSON.stringify(result)}`);
  return result.data;
}
async function postJson(path, body, csrf) {
  return evaluate(`(async () => {const r=await fetch(${JSON.stringify(path)},{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':${JSON.stringify(csrf)},'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(${JSON.stringify(body)})});const j=await r.json();return {status:r.status,code:j.error?.code,data:j.data};})()`);
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
      if (new URL(message.params.response.url).pathname === "/api/v1/auth/login"
        && message.params.response.status === 200) loginResponseId = message.params.requestId;
    }
    if (message.method === "Network.loadingFailed") observations.push({ loadingFailed: message.params.errorText });
    if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (message.method === "Network.requestWillBeSent" && message.params.request.method === "POST") {
      const path = new URL(message.params.request.url).pathname;
      if (path === validatePath && !validateRequest) validateRequest = message.params.request;
      if (path === submitPath && !submitRequest) submitRequest = message.params.request;
    }
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", "Synthetic Packaged User");
  await setValue("#login-password", "synthetic-packaged-login-password");
  await evaluate("document.querySelector('form button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  if (!loginResponseId) throw new Error("browser login response unavailable");
  const loginBody = await send("Network.getResponseBody", { requestId: loginResponseId });
  if (loginBody.base64Encoded) throw new Error("unexpected encoded login response");
  const csrf = JSON.parse(loginBody.body).data?.csrf_token;
  if (!/^[0-9a-f]{64}$/.test(csrf ?? "")) throw new Error("browser CSRF unavailable");
  const reviewBody = { reviewer_ids: [customer], policy_ref: "HANDOVER_ALL_V1",
    due_at: null, submission_note: null };
  const noAction = await postJson(submitPath, reviewBody, csrf);
  if (noAction.status !== 422 || noAction.code !== "BUSINESS_REVIEW_NOT_ELIGIBLE") {
    throw new Error(`missing Action not rejected: ${JSON.stringify(noAction)}`);
  }
  const due = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 19) + "Z";
  const action = await postJson(`/api/v1/projects/${project}/handover-action-items`, {
    source_analysis_version_ref: version, source_item_id: sourceItem, human_source_reason: null,
    action_type: "CONFIRM_DECISION", title: "Synthetic mapping decision follow-up",
    requested_input_spec: { fields: [{ name: "Old and new code mapping", format: "Two-column code table",
      example: "OLD-001 -> NEW-001", required: true }] }, owner_ref: customer,
    due_at: due, priority: "MEDIUM", created_reason: "Synthetic source-linked review prerequisite",
  }, csrf);
  if (action.status !== 201 || !uuid.test(action.data?.action_item_id ?? "")) {
    throw new Error(`source-linked Action creation failed: ${JSON.stringify(action)}`);
  }
  const ineligible = await postJson(submitPath, { ...reviewBody, reviewer_ids: [outsider] }, csrf);
  if (ineligible.status !== 422 || ineligible.code !== "BUSINESS_REVIEW_NOT_ELIGIBLE") {
    throw new Error(`unqualified reviewer not rejected: ${JSON.stringify(ineligible)}`);
  }
  const route = `/projects/${project}/handover/${analysis}`;
  await evaluate(`history.pushState({},'',${JSON.stringify(route)});dispatchEvent(new PopStateEvent('popstate'))`);
  await waitFor("document.querySelector('#handover-detail-title')&&document.body.innerText.includes('版本 1')", "DRAFT detail");
  await click("查看版本 1 的问题");
  await waitFor("document.querySelectorAll('article.issue-card').length===2&&document.querySelector('[aria-label=\"交接版本当前来源校验\"]')", "selected version");
  await click("运行当前来源校验");
  await waitFor("document.body.innerText.includes('本次校验通过；仍须独立送审与人工批准。')", "validation report");
  const validReplay = await replay(validatePath, validateRequest, 200);
  if (validReplay.valid !== true || validReplay.handover_analysis_version_id !== version
    || validReplay.blocking_issues?.length) throw new Error("validation replay not clean");
  await click("读取当前项目确认人");
  await waitFor(`document.body.innerText.includes('Synthetic Handover Customer')`, "current customer member");
  const chosen = await evaluate(`(() => {const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes('Synthetic Handover Customer'));if(!label)return false;const input=label.querySelector('input[type=checkbox]');if(!input||input.value!==${JSON.stringify(customer)})return false;input.click();return true;})()`);
  if (!chosen) throw new Error("current customer reviewer checkbox missing");
  const confirmed = await evaluate(`(() => {const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes('我已核对本固定版本'));if(!label)return false;label.querySelector('input[type=checkbox]').click();return true;})()`);
  if (!confirmed) throw new Error("review scope confirmation missing");
  await click("提交交接版本评审");
  await waitFor("document.body.innerText.includes('已送审，评审')", "IN_REVIEW submission");
  const submitReplay = await replay(submitPath, submitRequest, 201);
  if (submitReplay.state !== "IN_REVIEW" || submitReplay.handover_analysis_version_id !== version
    || submitReplay.reviewer_ids?.length !== 1 || submitReplay.reviewer_ids[0] !== customer) {
    throw new Error("review submission replay not identical");
  }
  const expectedDenied = observations.filter(item => item.url === submitPath && item.status === 422);
  const failures = observations.filter(item => item.exception || item.loadingFailed
    || item.status >= 400 && !(item.url === "/api/v1/auth/session" && item.status === 401)
    && !(item.url === submitPath && item.status === 422));
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  if (failures.length || alerts.length || expectedDenied.length !== 2) {
    throw new Error(`browser failures: ${JSON.stringify({ failures, alerts, expectedDenied })}`);
  }
  console.log(`HND_05_A04_P03_PACKAGED_EDGE_PASS: validation report, current customer, IN_REVIEW, same-key replays ${submitReplay.review_id}`);
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
