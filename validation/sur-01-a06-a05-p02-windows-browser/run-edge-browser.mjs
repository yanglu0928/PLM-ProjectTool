/** Real local Microsoft Edge/CDP proof for Survey source location UX. */
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, outputRoot] = process.argv.slice(2);
if (!origin?.startsWith("http://127.0.0.1:") || !outputRoot) throw new Error("owned browser arguments required");
await mkdir(outputRoot, { recursive: true });
const profile = await mkdtemp(join(tmpdir(), "plm-sur-a05-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1800", `${origin}/login`,
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
  throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,8000),resources:performance.getEntriesByType('resource').map(x=>x.name).filter(x=>x.includes('/api/')).slice(-20)})"))}`);
}
async function clickText(text) {
  const clicked = await evaluate(`(() => { const n=[...document.querySelectorAll('a,button')].find(x=>x.textContent.trim()===${JSON.stringify(text)});if(!n)return false;n.click();return true;})()`);
  if (!clicked) throw new Error(`Missing action: ${text}`);
}
async function clickLocation(index) {
  const clicked = await evaluate(`(() => { const n=[...document.querySelectorAll('button')].filter(x=>x.textContent.trim()==='定位该固定来源')[${index}];if(!n)return false;n.click();return true;})()`);
  if (!clicked) throw new Error(`Missing source location action ${index}`);
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
    if (message.method === "Network.responseReceived" && message.params.response.url.includes("/api/")) {
      observations.push({ url: message.params.response.url, status: message.params.response.status });
    }
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(() => { const set=(s,v)=>{const e=document.querySelector(s);const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value');d.set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));};set('#login-username','Synthetic Handover Manager');set('#login-password','synthetic-handover-browser-password');})()`);
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await clickText("我的项目"); await waitFor("document.body.innerText.includes('Survey schema')", "project list");
  await clickText("Survey schema"); await waitFor("document.body.innerText.includes('查看项目调研定义与问题卡片')", "project detail");
  await clickText("查看项目调研定义与问题卡片"); await waitFor("document.body.innerText.includes('浏览器来源定位调研')", "survey list");
  await clickText("查看版本、问题与来源说明"); await waitFor("document.body.innerText.includes('查看版本 1 的问题卡片')", "survey detail");
  await clickText("查看版本 1 的问题卡片");
  await waitFor("document.querySelectorAll('button').length && [...document.querySelectorAll('button')].filter(x=>x.textContent.trim()==='定位该固定来源').length===4", "four source buttons");
  const initial = await screenshot("01-question-source-buttons.png");

  await clickLocation(0);
  await waitFor("document.body.innerText.includes('打开交接分析中的固定问题') && document.body.innerText.includes('定位原文证据')", "Handover locations");
  await clickText("定位原文证据");
  await waitFor("document.body.innerText.includes('第 1 页 · 客户确认的交接范围') && document.body.innerText.includes('不是权威正文')", "Evidence Viewer location");
  const evidence = await screenshot("02-handover-evidence-location.png");

  await clickLocation(1);
  await waitFor("document.body.innerText.includes('当前项目身份无权展开其全局原文位置')", "Capability partial location");
  await clickLocation(2);
  await waitFor("document.body.innerText.includes('查看固定文档版本历史') && document.body.innerText.includes('打开受权固定版本原文')", "project template location");
  await clickLocation(3);
  await waitFor("document.body.innerText.includes('人工来源尚未绑定固定原文') && document.body.innerText.includes('访谈时间、参与人、结论及后续固定证据')", "manual guidance");
  const all = await screenshot("03-all-source-results.png");

  const safety = await evaluate(`(() => { const text=document.body.innerText; const links=[...document.querySelectorAll('a')].map(x=>x.getAttribute('href')); return { alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.innerText), rowId:text.includes('row_id'), templateContent:links.some(x=>x?.includes('/documents/')&&x?.includes('/versions/')&&x?.endsWith('/content')), evidenceContent:links.some(x=>x?.includes('/documents/')&&x?.includes('/versions/')&&x?.endsWith('/content')&&x?.includes('/api/v1/projects/')) }; })()`);
  if (safety.alerts.length || safety.rowId || !safety.templateContent || !safety.evidenceContent) throw new Error(`unsafe UI state: ${JSON.stringify(safety)}`);
  const locations = observations.filter(item => item.url.endsWith("/location") && item.status === 200);
  const viewers = observations.filter(item => item.url.includes("/evidence/") && item.url.endsWith("/viewer") && item.status === 200);
  if (locations.length !== 4 || viewers.length !== 1) throw new Error(`unexpected API evidence: ${JSON.stringify(observations)}`);
  console.log("SUR_01_A06_A05_P02_EDGE_BROWSER_PASS");
  console.log(JSON.stringify({ status: "PASS", screenshots: [initial, evidence, all], sourceResponses: locations.length,
    evidenceResponses: viewers.length, safety }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ observations }, null, 2)); throw error;
} finally {
  edge.kill(); await pause(300); await rm(profile, { recursive: true, force: true });
}
