/** Disposable packaged Edge proof: approved Handover row -> Survey DRAFT version. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, project, survey, actor] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "")
  || [project, survey, actor].some(value => !uuid.test(value ?? ""))) {
  throw new Error("synthetic HTTPS origin and canonical IDs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-survey-version-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", "--remote-debugging-address=127.0.0.1", `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--ignore-certificate-errors", "--window-size=1500,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const path = `/api/v1/projects/${project}/surveys/${survey}/versions`;
const observations = []; const pending = new Map(); let nextId = 0;
let socket; let createRequest = null; let createResponseId = null;
async function target() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try { const entries = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
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
      const url = new URL(message.params.response.url).pathname;
      observations.push({ url, status: message.params.response.status });
      if (url === path && message.params.response.status === 201 && !createResponseId) {
        createResponseId = message.params.requestId;
      }
    }
    if (message.method === "Network.loadingFailed") observations.push({ loadingFailed: message.params.errorText });
    if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (message.method === "Network.requestWillBeSent" && message.params.request.method === "POST"
      && new URL(message.params.request.url).pathname === path && !createRequest) {
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
  const route = `/projects/${project}/surveys/${survey}/versions/new`;
  await evaluate(`history.pushState({},'',${JSON.stringify(route)});dispatchEvent(new PopStateEvent('popstate'))`);
  await waitFor("document.querySelector('#survey-version-create-title')&&document.querySelectorAll('fieldset input[type=checkbox]').length>=2", "Survey version form");
  const warning = await evaluate("document.body.innerText");
  if (!warning.includes("实际面对面调研记录优先") || !warning.includes("不代表客户已确认")) {
    throw new Error("interview/customer boundary warning missing");
  }
  await evaluate("document.querySelectorAll('fieldset input[type=checkbox]')[0].click()");
  await evaluate("document.querySelectorAll('fieldset input[type=checkbox]')[1].click()");
  await setValue("input[placeholder='例如：当前物料审批流程']", "合成现场审批流程");
  await setValue("textarea[placeholder='写明确切的现场问题，不复制整篇资料']", "合成现场当前如何审批？");
  await setValue("textarea[placeholder='说明为什么需要询问及待澄清的边界']", "核对合成实际流程");
  await setValue("textarea[placeholder='例如：参与岗位、实际步骤、例外处理、待补证据']", "维护岗位与步骤");
  await setValue("textarea[placeholder^='写明访谈日期']", "2026-10-25合成面对面访谈；研发负责人参与，待客户核对。");
  const clicked = await evaluate("(() => {const x=[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='保存 DRAFT 调研问题版本');if(!x)return false;x.click();return true;})()");
  if (!clicked) throw new Error("Survey version save action missing");
  await waitFor("document.body.innerText.includes('已创建 DRAFT 版本')", "Survey version created");
  if (!createRequest || !createResponseId || !header(createRequest, "Idempotency-Key")
    || !header(createRequest, "If-Match") || !header(createRequest, "X-CSRF-Token")
    || !createRequest.postData) throw new Error("version Create request lacks key, etag, CSRF or body");
  const requestBody = JSON.parse(createRequest.postData);
  if (requestBody.questions?.length !== 1 || requestBody.target_department_ids?.length !== 1
    || requestBody.questions[0].sources?.length !== 2
    || requestBody.questions[0].sources[0].source_kind !== "HANDOVER_ITEM"
    || requestBody.questions[0].sources[1].source_kind !== "MANUAL") {
    throw new Error("browser did not submit fixed row plus explicit MANUAL interview note");
  }
  const body = await send("Network.getResponseBody", { requestId: createResponseId });
  if (body.base64Encoded) throw new Error("unexpected encoded SurveyVersion response");
  const created = JSON.parse(body.body).data;
  if (!uuid.test(created?.survey_version_id ?? "") || created.survey_id !== survey
    || created.project_id !== project || created.state !== "DRAFT" || created.version_no !== 1) {
    throw new Error(`Create response mismatch: ${JSON.stringify(created)}`);
  }
  const replay = await evaluate(`(async () => {const r=await fetch(${JSON.stringify(path)},{method:'POST',credentials:'same-origin',headers:${JSON.stringify({
    "X-CSRF-Token": header(createRequest, "X-CSRF-Token"),
    "Idempotency-Key": header(createRequest, "Idempotency-Key"),
    "If-Match": header(createRequest, "If-Match"),
    "Content-Type": "application/json",
  })},body:${JSON.stringify(createRequest.postData)}});const j=await r.json();return {status:r.status,data:j.data,code:j.error?.code};})()`);
  if (replay.status !== 201 || replay.data?.survey_version_id !== created.survey_version_id) {
    throw new Error(`same-key replay failed: ${JSON.stringify(replay)}`);
  }
  const failures = observations.filter(item => item.exception || item.loadingFailed
    || item.status >= 400 && !(item.url === "/api/v1/auth/session" && item.status === 401));
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  if (failures.length || alerts.length) throw new Error(`browser failures: ${JSON.stringify({ failures, alerts })}`);
  console.log(JSON.stringify({ status: "SUR_07_A08_PACKAGED_EDGE_PASS", project_id: project,
    survey_id: survey, actor_id: actor, survey_version_id: created.survey_version_id,
    handover_item_row_id: requestBody.questions[0].sources[0].handover_item_row_id,
    handover_analysis_version_id: requestBody.questions[0].sources[0].handover_analysis_version_id,
    target_department_id: requestBody.target_department_ids[0], request_body: requestBody,
    original_etag: header(createRequest, "If-Match") }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
