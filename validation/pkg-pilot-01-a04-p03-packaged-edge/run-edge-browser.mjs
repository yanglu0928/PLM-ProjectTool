/** Read-only packaged Edge UI proof under disposable synthetic HTTPS trust. */
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin] = process.argv.slice(2);
if (!/^https:\/\/localhost:\d+$/.test(origin ?? "")) throw new Error("synthetic HTTPS origin required");
const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profile = await mkdtemp(join(tmpdir(), "plm-pkg-a04p03-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn(edgePath, [
  "--headless=new", "--remote-debugging-address=127.0.0.1", `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--ignore-certificate-errors", "--window-size=1440,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket; let nextId = 0;
const pending = new Map();
const observations = [];
const routeResults = [];
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
  const id = ++nextId;
  socket.send(JSON.stringify({ id, method, params }));
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
  const state = await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,3000)})");
  throw new Error(`timeout ${label}: ${JSON.stringify(state)}`);
}
async function click(text) {
  const done = await evaluate(`(() => {const x=[...document.querySelectorAll('a,button')].find(e=>e.textContent.trim()===${JSON.stringify(text)});if(!x)return false;x.click();return true;})()`);
  if (!done) throw new Error(`missing UI action: ${text}`);
}
async function openFromDetail(linkText, heading) {
  await click(linkText);
  await waitFor(`document.querySelector('h1')?.textContent?.includes(${JSON.stringify(heading)})`, heading);
  await pause(300);
  await waitFor("![...document.querySelectorAll('[aria-busy=true]')].some(e=>e.offsetParent!==null)", `${heading} settled`);
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].filter(e=>e.offsetParent!==null).map(e=>e.innerText)");
  routeResults.push({ heading, alerts });
  await click("返回项目详情");
  await waitFor("document.querySelector('#project-title')?.textContent==='项目详情'", "project detail return");
  await waitFor("document.body.innerText.includes('查看项目六阶段流程')", "project links restored");
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
  await evaluate(`(() => {const set=(s,v)=>{const e=document.querySelector(s),d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));};set('#login-username','Synthetic Packaged User');set('#login-password','synthetic-packaged-login-password');})()`);
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await click("我的项目");
  await waitFor("document.body.innerText.includes('Synthetic packaged Workflow HTTPS')", "own project list");
  await click("Synthetic packaged Workflow HTTPS");
  await waitFor("document.body.innerText.includes('查看项目六阶段流程')", "project detail");
  const routes = [
    ["查看项目交接分析与待确认事项", "交接"],
    ["查看项目调研定义与问题卡片", "调研定义与固定版本"],
    ["查看项目需求、待维护内容与原文入口", "需求与固定版本"],
    ["维护项目原型、固定版本与需求覆盖", "原型范围与固定版本"],
    ["查看方案目录", "方案目录"],
    ["查看实施计划", "实施计划"],
  ];
  for (const [link, heading] of routes) await openFromDetail(link, heading);
  await click("查看项目六阶段流程");
  await waitFor("document.body.innerText.includes('流程状态：ACTIVE')&&document.body.innerText.includes('当前阶段：HANDOVER')&&document.body.innerText.includes('版本：\"v1\"')", "Workflow HANDOVER v1");
  await click("刷新当前流程");
  await waitFor("document.body.innerText.includes('流程状态：ACTIVE')&&document.body.innerText.includes('版本：\"v1\"')", "Workflow refreshed v1");
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  const screenshotSha256 = createHash("sha256").update(Buffer.from(shot.data, "base64")).digest("hex");
  const errors = observations.filter(item => item.exception || item.loadingFailed || item.status >= 400);
  if (errors.length || routeResults.some(item => item.alerts.length)) {
    throw new Error(`browser route/network/runtime errors: ${JSON.stringify({ routeResults, errors })}`);
  }
  if (!observations.some(item => item.url?.includes("/workflow") && item.status === 200)) {
    throw new Error("Workflow GET not observed in browser");
  }
  console.log("PKG_PILOT_01_A04_P03_EDGE_PASS");
  console.log(JSON.stringify({ status: "PASS", routes: routeResults,
    workflow: "HANDOVER/v1", apiResponses: observations.length, screenshotSha256 }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ error: String(error), routeResults, observations }, null, 2));
  process.exitCode = 1;
} finally {
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
