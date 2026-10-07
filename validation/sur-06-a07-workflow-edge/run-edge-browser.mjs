/** Real local Microsoft Edge proof for HANDOVER -> SURVEY -> REQUIREMENT. */
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, outputRoot] = process.argv.slice(2);
if (!origin?.startsWith("http://127.0.0.1:") || !outputRoot) throw new Error("owned browser arguments required");
await mkdir(outputRoot, { recursive: true });
const profile = await mkdtemp(join(tmpdir(), "plm-sur06-a07-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,2200",
  `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function target() {
  for (let count = 0; count < 100; count += 1) {
    try {
      const entries = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = entries.find(entry => entry.type === "page" && entry.url.startsWith(origin));
      if (page) return page;
    } catch { /* Edge starting. */ }
    await pause(100);
  }
  throw new Error("Edge DevTools target unavailable");
}
let socket; let id = 0; const pending = new Map(); const observations = [];
function send(method, params = {}) {
  const requestId = ++id;
  socket.send(JSON.stringify({ id: requestId, method, params }));
  return new Promise((resolve, reject) => pending.set(requestId, { resolve, reject }));
}
async function evaluate(expression) {
  const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
  return response.result.value;
}
async function waitFor(expression, label, attempts = 350) {
  for (let count = 0; count < attempts; count += 1) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await pause(100);
  }
  throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,10000)})"))}`);
}
async function clickText(text, index = 0) {
  const clicked = await evaluate(`(() => { const xs=[...document.querySelectorAll('a,button')].filter(x=>x.textContent.trim()===${JSON.stringify(text)});const n=xs[${index}];if(!n)return false;n.click();return true;})()`);
  if (!clicked) throw new Error(`Missing action: ${text}/${index}`);
}
async function screenshot(name) {
  const result = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  const path = join(outputRoot, name);
  await writeFile(path, Buffer.from(result.data, "base64"));
  return path;
}
async function refreshVersion(stage, version) {
  await clickText("刷新当前流程");
  await waitFor(`document.body.innerText.includes('当前阶段：${stage}')&&document.body.innerText.includes('版本："v${version}"')`, `${stage}/v${version}`);
}
async function recordPass(item, version) {
  const index = item.endsWith("ISSUES") || item.endsWith("CONCLUSION") ? 1 : 0;
  await clickText("核验并记录通过", index);
  await waitFor(`document.body.innerText.includes('确认记录 ${item} 为 PASS')`, `${item} preview`);
  const safe = await evaluate(`(() => { const f=document.querySelector('form[aria-label="检查项记录确认"]');return {uuid:/[0-9a-f]{8}-[0-9a-f-]{27}/i.test(f?.innerText??''),text:f?.innerText??''};})()`);
  if (safe.uuid || !safe.text.includes("服务器已按当前版本")) throw new Error(`unsafe qualification ${JSON.stringify(safe)}`);
  await evaluate(`document.querySelector('form[aria-label="检查项记录确认"] input[type=checkbox]').click()`);
  await waitFor("!document.querySelector('form[aria-label=\"检查项记录确认\"] button[type=submit]').disabled", `${item} submit enabled`);
  await evaluate(`document.querySelector('form[aria-label="检查项记录确认"] button[type=submit]').click()`);
  await waitFor(`document.body.innerText.includes('首次检查项回执：${item} · PASS · "v${version}"')`, `${item} receipt`);
  await refreshVersion(item.startsWith("HANDOVER") ? "HANDOVER" : "SURVEY", version);
}
async function transition(from, to, version, reason) {
  await clickText(`准备推进至 ${to}`);
  await waitFor(`document.body.innerText.includes('确认从 ${from} 推进至 ${to}')`, `${from} transition form`);
  await evaluate(`(() => { const f=document.querySelector('form[aria-label="阶段推进确认"]'),t=f.querySelector('textarea'),d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(t),'value');d.set.call(t,${JSON.stringify(reason)});t.dispatchEvent(new Event('input',{bubbles:true}));f.querySelector('input[type=checkbox]').click();})()`);
  await waitFor("!document.querySelector('form[aria-label=\"阶段推进确认\"] button[type=submit]').disabled", `${from} transition submit enabled`);
  await evaluate(`document.querySelector('form[aria-label="阶段推进确认"] button[type=submit]').click()`);
  await waitFor(`document.body.innerText.includes('首次阶段推进回执：${from} → ${to} · "v${version}"')`, `${from} transition receipt`);
  await refreshVersion(to, version);
}
try {
  const page = await target(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === "Network.responseReceived" && message.params.response.url.includes("/api/")) {
      observations.push({ url: message.params.response.url, status: message.params.response.status });
    }
    if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(() => { const set=(s,v)=>{const e=document.querySelector(s),d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));};set('#login-username','Synthetic Handover Manager');set('#login-password','synthetic-handover-browser-password');})()`);
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await clickText("我的项目"); await waitFor("document.body.innerText.includes('Survey schema')", "project list");
  await clickText("Survey schema"); await waitFor("document.body.innerText.includes('查看项目六阶段流程')", "project detail");
  await clickText("查看项目六阶段流程");
  await waitFor("document.body.innerText.includes('流程状态：NOT_STARTED')&&document.body.innerText.includes('版本：\"v0\"')", "workflow v0");
  await clickText("准备启动流程");
  await evaluate(`(() => { const f=[...document.querySelectorAll('form')].find(x=>x.textContent.includes('确认启动项目流程'));f.querySelector('input[type=checkbox]').click();})()`);
  await waitFor("![...document.querySelectorAll('form')].find(x=>x.textContent.includes('确认启动项目流程')).querySelector('button[type=submit]').disabled", "start enabled");
  await evaluate(`[...document.querySelectorAll('form')].find(x=>x.textContent.includes('确认启动项目流程')).querySelector('button[type=submit]').click()`);
  await waitFor("document.body.innerText.includes('首次启动回执：HANDOVER · \"v1\"')", "start receipt");
  await refreshVersion("HANDOVER", 1);
  await recordPass("HANDOVER_BASELINE", 2);
  await recordPass("HANDOVER_ISSUES", 3);
  const handover = await screenshot("01-handover-two-pass-v3.png");
  await transition("HANDOVER", "SURVEY", 4, "交接事实已核对");
  await recordPass("SURVEY_ACTUAL_SOURCES", 5);
  await recordPass("SURVEY_CONCLUSION", 6);
  const survey = await screenshot("02-survey-two-pass-v6.png");
  await transition("SURVEY", "REQUIREMENT", 7, "调研事实已核对");
  const final = await screenshot("03-requirement-v7.png");
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(x=>x.offsetParent!==null).map(x=>x.innerText)");
  const required = ["/workflow:start", "HANDOVER_BASELINE:record", "HANDOVER_ISSUES:record",
    "SURVEY_ACTUAL_SOURCES:record", "SURVEY_CONCLUSION:record", "/workflow:transition"];
  const missing = required.filter(part => !observations.some(item => item.url?.includes(part) && item.status >= 200 && item.status < 300));
  if (alerts.length || missing.length || observations.some(item => item.exception)) throw new Error(`browser proof mismatch ${JSON.stringify({ alerts, missing, observations })}`);
  console.log("SUR_06_A07_EDGE_BROWSER_PASS");
  console.log(JSON.stringify({ status: "PASS", screenshots: [handover, survey, final], observations: observations.length }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ observations }, null, 2)); throw error;
} finally {
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
