/** Real local Microsoft Edge/CDP proof for Stage Transition. */
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, outputRoot] = process.argv.slice(2);
if (!origin?.startsWith("http://127.0.0.1:") || !outputRoot) throw new Error("owned browser arguments required");
await mkdir(outputRoot, { recursive: true });
const profile = await mkdtemp(join(tmpdir(), "plm-wfl-a07-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1600", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function target() {
  for (let count = 0; count < 100; count += 1) {
    try {
      const entries = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = entries.find(entry => entry.type === "page" && entry.url.startsWith(origin));
      if (page) return page;
    } catch { /* starting */ }
    await pause(100);
  }
  throw new Error("Edge DevTools target unavailable");
}
let socket; let id = 0; const pending = new Map(); const observations = [];
function send(method, params = {}) {
  const requestId = ++id; socket.send(JSON.stringify({ id: requestId, method, params }));
  return new Promise((resolve, reject) => pending.set(requestId, { resolve, reject }));
}
async function evaluate(expression) {
  const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
  return response.result.value;
}
async function waitFor(expression, label) {
  for (let count = 0; count < 250; count += 1) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await pause(100);
  }
  throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,6000)})"))}`);
}
async function clickText(text) {
  const clicked = await evaluate(`(() => { const n=[...document.querySelectorAll('a,button')].find(x=>x.textContent.trim()===${JSON.stringify(text)}); if(!n)return false;n.click();return true;})()`);
  if (!clicked) throw new Error(`Missing action: ${text}`);
}
async function screenshot(name) {
  const result = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  const path = join(outputRoot, name); await writeFile(path, Buffer.from(result.data, "base64")); return path;
}
try {
  const page = await target(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === "Network.responseReceived" && message.params.response.url.includes("/api/")) observations.push({ url: message.params.response.url, status: message.params.response.status });
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(() => { const set=(s,v)=>{const e=document.querySelector(s);const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));};set('#login-username','Synthetic Handover Manager');set('#login-password','synthetic-handover-browser-password');})()`);
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await clickText("我的项目"); await waitFor("document.body.innerText.includes('Qualification')", "project list");
  await clickText("Qualification"); await waitFor("document.body.innerText.includes('查看项目六阶段流程')", "project detail");
  await clickText("查看项目六阶段流程");
  await waitFor("document.body.innerText.includes('HANDOVER_BASELINE · PASS') && document.body.innerText.includes('HANDOVER_ISSUES · PASS') && document.body.innerText.includes('版本：\"v3\"')", "two PASS records");
  await clickText("准备推进至 SURVEY");
  await waitFor("document.querySelector('form[aria-label=\"阶段推进确认\"]')", "transition form");
  const preview = await evaluate(`(() => { const f=document.querySelector('form[aria-label="阶段推进确认"]');return {text:f?.innerText??'',uuid:/[0-9a-f]{8}-[0-9a-f-]{27}/i.test(f?.innerText??'')};})()`);
  if (!preview.text.includes("服务器会在提交事务中重新验证") || preview.uuid) throw new Error(`unsafe transition preview: ${JSON.stringify(preview)}`);
  const before = await screenshot("01-transition-confirmation.png");
  await evaluate(`(() => { const f=document.querySelector('form[aria-label="阶段推进确认"]');const t=f.querySelector('textarea');const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(t),'value');d.set.call(t,'交接事实已核对');t.dispatchEvent(new Event('input',{bubbles:true}));f.querySelector('input[type=checkbox]').click();})()`);
  await waitFor("!document.querySelector('form[aria-label=\"阶段推进确认\"] button[type=submit]')?.disabled", "enabled transition submit");
  await evaluate("document.querySelector('form[aria-label=\"阶段推进确认\"] button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('首次阶段推进回执：HANDOVER → SURVEY · \"v4\"')", "first transition receipt");
  const receipt = await screenshot("02-first-transition-receipt.png");
  await clickText("刷新当前流程");
  await waitFor("document.body.innerText.includes('当前阶段：SURVEY') && document.body.innerText.includes('版本：\"v4\"') && document.body.innerText.includes('HANDOVER · COMPLETED') && document.body.innerText.includes('SURVEY · ACTIVE')", "independent SURVEY refresh");
  const current = await screenshot("03-current-survey-v4.png");
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].map(x=>x.innerText)");
  if (alerts.length) throw new Error(`Unexpected UI alerts: ${JSON.stringify(alerts)}`);
  const successful = observations.filter(item => item.status >= 200 && item.status < 300);
  if (!successful.some(item => item.url.includes("/workflow:transition"))) throw new Error(`Transition response missing: ${JSON.stringify(observations)}`);
  console.log("WFL_02_A02_A07_EDGE_BROWSER_PASS");
  console.log(JSON.stringify({ status: "PASS", screenshots: [before, receipt, current], apiResponses: successful.length }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ observations }, null, 2)); throw error;
} finally {
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
