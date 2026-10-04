/** Real local Edge fallback when the managed browser kernel is unavailable. */
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, projectId, indexId, outputRoot] = process.argv.slice(2);
if (!origin?.startsWith("http://127.0.0.1:") || !/^[0-9a-f-]{36}$/.test(projectId ?? "")
    || !/^[0-9a-f-]{36}$/.test(indexId ?? "") || !outputRoot) {
  throw new Error("origin, project id, index id and output root required");
}
await mkdir(outputRoot, { recursive: true });
const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profile = await mkdtemp(join(tmpdir(), "plm-rag-p08-edge-"));
const debuggingPort = 10000 + (process.pid % 40000);
const browser = spawn(edge, [
  "--headless=new", `--remote-debugging-port=${debuggingPort}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--window-size=1440,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function target() {
  for (let count = 0; count < 100; count += 1) {
    try {
      const entries = await (await fetch(`http://127.0.0.1:${debuggingPort}/json/list`)).json();
      const page = entries.find((entry) => entry.type === "page" && entry.url.startsWith(origin));
      if (page) return page;
    } catch { /* Edge is starting. */ }
    await pause(100);
  }
  throw new Error("Edge DevTools target unavailable");
}

let socket;
let nextId = 0;
const pending = new Map();
const observations = [];
function send(method, params = {}) {
  const id = ++nextId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
async function evaluate(expression) {
  const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
  return response.result.value;
}
async function waitFor(expression, label, attempts = 200) {
  for (let count = 0; count < attempts; count += 1) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await pause(100);
  }
  const diagnostic = await evaluate("({ url: location.href, text: document.body?.innerText?.slice(0, 5000) ?? '' })");
  throw new Error(`Timed out waiting for ${label}: ${JSON.stringify({ diagnostic, observations: observations.slice(-30) })}`);
}
async function clickText(text) {
  const clicked = await evaluate(`(() => { const node = [...document.querySelectorAll('a,button')]
    .find((item) => item.textContent.trim() === ${JSON.stringify(text)}); if (!node) return false; node.click(); return true; })()`);
  if (!clicked) throw new Error(`Missing action: ${text}`);
}
async function screenshot(name) {
  const result = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  const path = join(outputRoot, name);
  await writeFile(path, Buffer.from(result.data, "base64"));
  return path;
}
async function fillCreate(query) {
  const filled = await evaluate(`(() => {
    const set = (element, value) => {
      const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value');
      descriptor.set.call(element, value); element.dispatchEvent(new Event('input', { bubbles: true }));
    };
    const query = document.querySelector('textarea');
    const index = document.querySelector('input[maxlength="36"]');
    const source = document.querySelector('input[value="PROJECT_RECORD"]');
    if (!query || !index || !source) return false;
    set(query, ${JSON.stringify(query)}); set(index, ${JSON.stringify(indexId)});
    if (!source.checked) source.click(); return true;
  })()`);
  if (!filled) throw new Error("Retrieval form controls unavailable");
  await pause(100);
  const confirmed = await evaluate(`(() => { const confirm = document.querySelector('.confirm input[type="checkbox"]');
    if (!confirm) return false; if (!confirm.checked) confirm.click(); return confirm.checked; })()`);
  if (!confirmed) throw new Error("Retrieval confirmation unavailable");
  await waitFor("!document.querySelector('button[type=submit]').disabled", "enabled retrieval submit");
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("location.pathname.match(/\\/retrievals\\/[0-9a-f-]{36}$/) && document.body.innerText.includes('正在检索')", "running retrieval");
  return evaluate("location.pathname.split('/').at(-1)");
}

try {
  const page = await target();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === "Network.responseReceived") {
      const response = message.params.response;
      if (response.url.includes("/api/")) observations.push({ url: response.url, status: response.status });
    } else if (message.method === "Runtime.exceptionThrown") {
      observations.push({ exception: message.params.exceptionDetails.text });
    }
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(() => { const set = (selector, value) => { const input = document.querySelector(selector);
    const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value');
    descriptor.set.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })); };
    set('#login-username', 'Synthetic Retrieval Manager');
    set('#login-password', 'synthetic-rag-browser-password'); return true; })()`);
  await waitFor("!document.querySelector('button[type=submit]').disabled", "enabled login action");
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "successful login");

  const createUrl = `${origin}/projects/${projectId}/retrievals/new`;
  await clickText("我的项目");
  await waitFor("document.body.innerText.includes('Synthetic RAG Source')", "project list");
  await clickText("Synthetic RAG Source");
  await waitFor("document.body.innerText.includes('新建项目知识检索')", "project detail");
  await clickText("新建项目知识检索");
  await waitFor(`location.href === ${JSON.stringify(createUrl)} && document.body.innerText.includes('新建项目内 FTS 检索')`, "retrieval create page");
  const succeededRun = await fillCreate("PLM");
  const runningShot = await screenshot("01-running.png");
  console.log(`RAG_BROWSER_CREATED ${succeededRun}`);

  for (let count = 0; count < 600; count += 1) {
    await clickText("刷新检索状态");
    await pause(200);
    if (await evaluate("document.body.innerText.includes('授权检索结果') && document.body.innerText.includes('最小上下文')")) break;
    if (count === 599) throw new Error("Succeeded Result/Context did not appear");
  }
  const success = await evaluate(`(() => ({ url: location.href, text: document.body.innerText,
    local: Object.keys(localStorage), session: Object.keys(sessionStorage),
    alerts: [...document.querySelectorAll('[role=alert]')].map((item) => item.innerText) }))()`);
  if (success.alerts.length || success.url.includes("PLM") || success.local.length || success.session.length
      || !success.text.includes("PLM begin one") || !success.text.includes("PROJECT_RECORD")
      || !success.text.includes("fts.project.v1") || success.text.includes("bundle_fingerprint")) {
    throw new Error(`Unexpected successful retrieval view: ${JSON.stringify(success)}`);
  }
  const successShot = await screenshot("02-result-context.png");

  await clickText("返回项目详情");
  await waitFor("document.body.innerText.includes('新建项目知识检索')", "project detail after result");
  await clickText("新建项目知识检索");
  await waitFor(`location.href === ${JSON.stringify(createUrl)} && document.body.innerText.includes('新建项目内 FTS 检索')`, "second retrieval create page");
  const cancelledRun = await fillCreate("PLM cancel request");
  const cancelFilled = await evaluate(`(() => {
    const reason = document.querySelector('form textarea');
    const confirm = document.querySelector('form .confirm input[type="checkbox"]');
    if (!reason || !confirm) return false;
    const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(reason), 'value');
    descriptor.set.call(reason, '合成浏览器取消验收'); reason.dispatchEvent(new Event('input', { bubbles: true }));
    if (!confirm.checked) confirm.click(); return true;
  })()`);
  if (!cancelFilled) throw new Error("Cancel form controls unavailable");
  await clickText("提交取消请求");
  await waitFor("document.body.innerText.includes('取消首次回执：已取消') || document.body.innerText.includes('取消首次回执：CANCELLED')", "cancel receipt");
  await clickText("刷新检索状态");
  await waitFor("document.body.innerText.includes('状态\\n已取消')", "cancelled current state");
  const cancelled = await evaluate(`(() => ({ url: location.href, text: document.body.innerText,
    alerts: [...document.querySelectorAll('[role=alert]')].map((item) => item.innerText) }))()`);
  if (cancelled.alerts.length || !cancelled.url.endsWith(cancelledRun) || !cancelled.text.includes("已取消")) {
    throw new Error(`Unexpected cancelled retrieval view: ${JSON.stringify(cancelled)}`);
  }
  const cancelShot = await screenshot("03-cancelled.png");
  const api = observations.filter((item) => item.url);
  const required = ["/retrieval-runs", `/${succeededRun}/result`, `/${succeededRun}/context`, `/${cancelledRun}:cancel`];
  const missing = required.filter((part) => !api.some((item) => item.status >= 200 && item.status < 300 && item.url.includes(part)));
  if (missing.length) throw new Error(`Missing successful API observations: ${JSON.stringify({ missing, api })}`);
  console.log("RAG_04_A06_P08_EDGE_BROWSER_PASS");
  console.log(JSON.stringify({ status: "PASS", succeededRun, cancelledRun,
    screenshots: [runningShot, successShot, cancelShot], apiResponses: api.length }));
  socket.close();
} finally {
  browser.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
