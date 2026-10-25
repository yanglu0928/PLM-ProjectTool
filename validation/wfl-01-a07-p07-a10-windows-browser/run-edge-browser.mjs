/** Real local Edge fallback when the managed Windows browser kernel is unavailable. */
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, outputRoot] = process.argv.slice(2);
if (!origin?.startsWith("http://127.0.0.1:") || !outputRoot) {
  throw new Error("owned browser arguments required");
}
await mkdir(outputRoot, { recursive: true });
const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profile = await mkdtemp(join(tmpdir(), "plm-wfl-a10-edge-"));
const debuggingPort = 10000 + (process.pid % 40000);
const processHandle = spawn(edge, [
  "--headless=new", `--remote-debugging-port=${debuggingPort}`,
  `--user-data-dir=${profile}`, "--no-first-run",
  "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1600",
  `${origin}/login`,
], { stdio: "ignore", windowsHide: true });
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function target() {
  for (let count = 0; count < 100; count += 1) {
    try {
      const entries = await (await fetch(`http://127.0.0.1:${debuggingPort}/json/list`)).json();
      const page = entries.find(entry => entry.type === "page" && entry.url.startsWith(origin));
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
  const response = await send("Runtime.evaluate", {
    expression, awaitPromise: true, returnByValue: true,
  });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
  return response.result.value;
}
async function waitFor(expression, label, attempts = 250) {
  for (let count = 0; count < attempts; count += 1) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await pause(100);
  }
  throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,6000)})",
  ))}`);
}
async function clickText(text) {
  const clicked = await evaluate(`(() => { const node=[...document.querySelectorAll('a,button')]
    .find(item=>item.textContent.trim()===${JSON.stringify(text)});
    if(!node)return false; node.click(); return true; })()`);
  if (!clicked) throw new Error(`Missing action: ${text}`);
}
async function screenshot(name) {
  const result = await send("Page.captureScreenshot", {
    format: "png", captureBeyondViewport: true,
  });
  const path = join(outputRoot, name);
  await writeFile(path, Buffer.from(result.data, "base64"));
  return path;
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
      if (response.url.includes("/api/")) {
        observations.push({ url: response.url, status: response.status });
      }
    } else if (message.method === "Runtime.exceptionThrown") {
      observations.push({ exception: message.params.exceptionDetails.text });
    }
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(() => { const set=(selector,value)=>{const element=document.querySelector(selector);
    const descriptor=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element),'value');
    descriptor.set.call(element,value); element.dispatchEvent(new Event('input',{bubbles:true}));};
    set('#login-username','Synthetic Handover Manager');
    set('#login-password','synthetic-handover-browser-password'); return true; })()`);
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await clickText("我的项目");
  await waitFor("document.body.innerText.includes('Qualification')", "project list");
  await clickText("Qualification");
  await waitFor("document.body.innerText.includes('查看项目六阶段流程')", "project detail");
  await clickText("查看项目六阶段流程");
  await waitFor("document.body.innerText.includes('HANDOVER_ISSUES · PENDING')", "workflow pending state");
  const opened = await evaluate(`(() => { const row=[...document.querySelectorAll('li')]
    .find(item=>item.childNodes[0]?.textContent?.includes('HANDOVER_ISSUES'));
    const button=[...(row?.querySelectorAll('button')??[])].find(item=>item.textContent.trim()==='核验并记录通过');
    if(!button)return false; button.click(); return true; })()`);
  if (!opened) throw new Error("HANDOVER_ISSUES PASS action unavailable");
  await waitFor("document.querySelector('form[aria-label=\"检查项记录确认\"]')?.innerText.includes('服务器已按当前版本')", "qualification preview");
  const preview = await evaluate(`(() => { const form=document.querySelector('form[aria-label="检查项记录确认"]');
    return {text:form?.innerText??'', uuid:/[0-9a-f]{8}-[0-9a-f-]{27}/i.test(form?.innerText??'')}; })()`);
  if (!preview.text.includes("项固定依据") || preview.uuid) {
    throw new Error(`qualification preview leaked or omitted facts: ${JSON.stringify(preview)}`);
  }
  const previewShot = await screenshot("01-qualification-preview.png");
  const confirmed = await evaluate(`(() => { const form=document.querySelector('form[aria-label="检查项记录确认"]');
    const checkbox=form?.querySelector('input[type=checkbox]'); if(!checkbox)return false;
    checkbox.click(); return true; })()`);
  if (!confirmed) throw new Error("Checklist confirmation form unavailable");
  await waitFor("!document.querySelector('form[aria-label=\"检查项记录确认\"] button[type=submit]')?.disabled", "enabled checklist submit");
  await evaluate("document.querySelector('form[aria-label=\"检查项记录确认\"] button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('首次检查项回执：HANDOVER_ISSUES · PASS · \\\"v2\\\"')", "first PASS receipt");
  const receiptShot = await screenshot("02-first-pass-receipt.png");
  await clickText("刷新当前流程");
  await waitFor("document.body.innerText.includes('HANDOVER_ISSUES · PASS') && document.body.innerText.includes('版本：\\\"v2\\\"')", "independent v2 refresh");
  const currentShot = await screenshot("03-current-pass-v2.png");
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].map(item=>item.innerText)");
  if (alerts.length) throw new Error(`Unexpected UI alerts: ${JSON.stringify(alerts)}`);
  const successful = observations.filter(item => item.status >= 200 && item.status < 300);
  const required = [
    "/api/v1/projects/",
    "/workflow",
    "/HANDOVER_ISSUES/qualification",
    "/HANDOVER_ISSUES:record",
  ];
  const missing = required.filter(part => !successful.some(item => item.url.includes(part)));
  if (missing.length) {
    throw new Error(`Missing successful API observations: ${JSON.stringify({ missing, observations })}`);
  }
  console.log("WFL_01_A07_P07_A10_EDGE_BROWSER_PASS");
  console.log(JSON.stringify({
    status: "PASS", screenshots: [previewShot, receiptShot, currentShot],
    apiResponses: successful.length,
  }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ observations }, null, 2));
  throw error;
} finally {
  processHandle.kill();
  await pause(300);
  await rm(profile, { recursive: true, force: true });
}
