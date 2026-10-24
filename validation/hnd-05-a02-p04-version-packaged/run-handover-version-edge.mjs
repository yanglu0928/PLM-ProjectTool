/** Disposable packaged Edge proof of a grounded two-card Handover DRAFT version. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, project, analysis] = process.argv.slice(2);
const id = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "") || !id.test(project ?? "") || !id.test(analysis ?? "")) {
  throw new Error("synthetic HTTPS origin/project/analysis required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-hnd-version-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", "--remote-debugging-address=127.0.0.1", `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--ignore-certificate-errors", "--window-size=1500,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket; let nextId = 0; const pending = new Map(); const observations = [];
let versionRequest = null;
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
async function setValue(selector, value, event = "input") {
  const done = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event(${JSON.stringify(event)},{bubbles:true}));return true;})()`);
  if (!done) throw new Error(`missing input: ${selector}`);
}
async function setCard(index, selector, value, event = "input") {
  const done = await evaluate(`(() => {const a=document.querySelectorAll('article.issue-card')[${index}],e=a?.querySelector(${JSON.stringify(selector)});if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event(${JSON.stringify(event)},{bubbles:true}));return true;})()`);
  if (!done) throw new Error(`missing card input ${index}: ${selector}`);
}
async function setCardArea(index, ordinal, value) {
  const done = await evaluate(`(() => {const e=document.querySelectorAll('article.issue-card')[${index}]?.querySelectorAll('textarea')[${ordinal}];if(!e)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`);
  if (!done) throw new Error(`missing card textarea ${index}/${ordinal}`);
}
async function clickCard(index, selector) {
  const done = await evaluate(`(() => {const e=document.querySelectorAll('article.issue-card')[${index}]?.querySelector(${JSON.stringify(selector)});if(!e)return false;e.click();return true;})()`);
  if (!done) throw new Error(`missing card choice ${index}: ${selector}`);
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
    if (message.method === "Network.requestWillBeSent"
      && new URL(message.params.request.url).pathname === `/api/v1/projects/${project}/handover-analyses/${analysis}/versions`
      && message.params.request.method === "POST" && !versionRequest) versionRequest = message.params.request;
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
  const route = `/projects/${project}/handover/${analysis}/versions/new`;
  await evaluate(`history.pushState({},'',${JSON.stringify(route)});dispatchEvent(new PopStateEvent('popstate'))`);
  await waitFor("document.querySelector('#handover-version-create-title')&&document.body.innerText.includes('Synthetic Handover Source')", "handover source list");
  await click("选择固定版本");
  await waitFor("[...document.querySelectorAll('button')].some(e=>e.textContent.trim()==='选用此固定版本')", "fixed version choice");
  await click("选用此固定版本");
  await waitFor("document.body.innerText.includes('固定来源与原分析完全匹配')", "browser source-set hash");
  const selected = await evaluate(`(() => {const li=[...document.querySelectorAll('li')].find(e=>e.textContent.includes('Synthetic Multi Baseline'));const b=[...li?.querySelectorAll('button')??[]].find(e=>e.textContent.trim()==='选用已批准版');if(!b)return false;b.click();return true;})()`);
  if (!selected) throw new Error("approved Capability baseline not listed");
  await waitFor("document.body.innerText.includes('已选 Synthetic Multi Baseline')", "current approved Capability");
  await waitFor("document.body.innerText.includes('Synthetic Project Handover Evidence')", "eligible Project Evidence");
  await setCard(0, 'input[placeholder="例如：物料编码映射规则待确认"]', "Synthetic grounded interface gap");
  await setCardArea(0, 0, "Synthetic checked gap based on fixed project source");
  await setCardArea(0, 1, "Synthetic mapping impact");
  await clickCard(0, "fieldset:first-of-type input[type=checkbox]");
  await click("定位原文");
  await waitFor("document.body.innerText.includes('打开受权固定版本')", "authorized Evidence locator");
  await click("增加一张问题卡片");
  await waitFor("document.querySelectorAll('article.issue-card').length===2", "second issue card");
  await setCard(1, "select", "NEED_CONFIRM", "change");
  await waitFor("document.querySelectorAll('article.issue-card')[1].querySelectorAll('textarea').length===4", "confirmation guidance");
  await setCard(1, 'input[placeholder="例如：物料编码映射规则待确认"]', "Synthetic mapping decision needed");
  await setCardArea(1, 0, "Synthetic source leaves mapping open");
  await setCardArea(1, 1, "Synthetic migration impact");
  await setCardArea(1, 2, "Request authorized business decision");
  await setCardArea(1, 3, "Which mapping approach should be used?");
  await setCard(1, 'input[placeholder="例如：旧编码、新编码、映射负责人"]', "Old and new code mapping");
  await setCard(1, 'input[placeholder="例如：两列编码对照表"]', "Two-column code table");
  await setCard(1, 'input[placeholder="例如：OLD-001 → NEW-001（仅示例）"]', "OLD-001 -> NEW-001");
  await setCard(1, 'input[placeholder="例如：沿用旧编码并建立映射"]', "Retain old code with mapping");
  await setCard(1, 'input[placeholder="例如：统一切换新编码"]', "Switch to new code");
  await clickCard(1, "fieldset:first-of-type input[type=checkbox]");
  await click("保存 DRAFT 问题版本");
  await waitFor("document.querySelector('#handover-detail-title')&&document.body.innerText.includes('版本 1')", "created DRAFT detail");
  await click("查看版本 1 的问题");
  await waitFor("document.querySelectorAll('article.issue-card').length===2", "two persisted issue cards");
  const header = name => Object.entries(versionRequest?.headers ?? {})
    .find(([key]) => key.toLowerCase() === name.toLowerCase())?.[1];
  if (!versionRequest?.postData || !header("Idempotency-Key")
    || !header("X-CSRF-Token") || !header("If-Match")) {
    throw new Error("original browser version command unavailable for replay");
  }
  const replay = await evaluate(`(async () => {const r=await fetch(${JSON.stringify(`/api/v1/projects/${project}/handover-analyses/${analysis}/versions`)},{method:'POST',credentials:'same-origin',headers:${JSON.stringify({
    "Content-Type": "application/json", "X-CSRF-Token": header("X-CSRF-Token"),
    "Idempotency-Key": header("Idempotency-Key"), "If-Match": header("If-Match"),
  })},body:${JSON.stringify(versionRequest.postData)}});return {status:r.status,data:(await r.json()).data};})()`);
  if (replay.status !== 201 || !id.test(replay.data?.handover_analysis_version_id ?? "")) {
    throw new Error(`original operation replay failed: ${JSON.stringify(replay)}`);
  }
  const failures = observations.filter(item => item.exception || item.loadingFailed || item.status >= 400
    && !(item.url === "/api/v1/auth/session" && item.status === 401));
  const posts = observations.filter(item => item.url === `/api/v1/projects/${project}/handover-analyses/${analysis}/versions`
    && item.status === 201);
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  if (failures.length || alerts.length || posts.length !== 2) {
    throw new Error(`Handover version browser mismatch: ${JSON.stringify({ failures, alerts, observations })}`);
  }
  console.log(`HND_05_A02_P04_PACKAGED_EDGE_PASS: two grounded DRAFT cards, same-key replay, ${replay.data.handover_analysis_version_id}`);
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), observations }, null, 2)); process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
