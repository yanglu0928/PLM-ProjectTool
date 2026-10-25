/** Real local Edge fallback when the managed Windows browser kernel is unavailable. */
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, projectId, actorId, documentId, versionId, submissionId, verificationId, outputRoot] = process.argv.slice(2);
if (!origin?.startsWith("http://127.0.0.1:") || ![projectId, actorId, documentId, versionId, submissionId, verificationId]
    .every((value) => /^[0-9a-f-]{36}$/.test(value ?? "")) || !outputRoot) throw new Error("owned browser arguments required");
await mkdir(outputRoot, { recursive: true });
const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profile = await mkdtemp(join(tmpdir(), "plm-hnd-a06-edge-"));
const debuggingPort = 10000 + (process.pid % 40000);
const processHandle = spawn(edge, ["--headless=new", `--remote-debugging-port=${debuggingPort}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1300", `${origin}/login`],
{ stdio: "ignore", windowsHide: true });
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function target() { for (let count = 0; count < 100; count += 1) { try { const entries = await (await fetch(`http://127.0.0.1:${debuggingPort}/json/list`)).json();
  const page = entries.find(entry => entry.type === "page" && entry.url.startsWith(origin)); if (page) return page; } catch { /* starting */ } await pause(100); }
  throw new Error("Edge DevTools target unavailable"); }
let socket; let nextId = 0; const pending = new Map(); const observations = [];
function send(method, params = {}) { const id = ++nextId; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject })); }
async function evaluate(expression) { const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text); return response.result.value; }
async function waitFor(expression, label, attempts = 250) { for (let count = 0; count < attempts; count += 1) {
  if (await evaluate(`Boolean(${expression})`)) return; await pause(100); }
  throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,5000)})"))}`); }
async function clickText(text, container = "document") { const clicked = await evaluate(`(() => { const root=${container}; const node=[...root.querySelectorAll('a,button')]
  .find(item=>item.textContent.trim()===${JSON.stringify(text)}); if(!node)return false; node.click(); return true; })()`);
  if (!clicked) throw new Error(`Missing action: ${text}`); }
async function setLabel(label, value, selector = "input,textarea,select") { const changed = await evaluate(`(() => { const label=[...document.querySelectorAll('label')]
  .find(item=>item.textContent.trim().startsWith(${JSON.stringify(label)})); const element=label?.querySelector(${JSON.stringify(selector)}); if(!element)return false;
  const descriptor=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element),'value'); descriptor.set.call(element,${JSON.stringify(value)});
  element.dispatchEvent(new Event('input',{bubbles:true})); element.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`);
  if (!changed) throw new Error(`Missing field: ${label}`); }
async function screenshot(name) { const result = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  const path = join(outputRoot, name); await writeFile(path, Buffer.from(result.data, "base64")); return path; }
async function openAction(title) { const opened = await evaluate(`(() => { const li=[...document.querySelectorAll('ol[aria-label="交接待办"] li')]
  .find(item=>item.textContent.includes(${JSON.stringify(title)})); const button=li?.querySelector('button'); if(!button)return false; button.click(); return true; })()`);
  if (!opened) throw new Error(`Action not found: ${title}`); await waitFor(`document.querySelector('.action-detail')?.textContent.includes(${JSON.stringify(title)})`, `detail ${title}`); }
async function submitVisibleForm() { const submitted = await evaluate(`(() => { const forms=[...document.querySelectorAll('form.write-panel')]
  .filter(item=>item.offsetParent!==null); const form=forms.at(-1); if(!form)return false; form.querySelector('button[type=submit]').click(); return true; })()`);
  if (!submitted) throw new Error("Visible write form unavailable"); }
const due = new Date(Date.now() + 7 * 86400000); const localDue = new Date(due.valueOf() - due.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
async function createAction(title) { await clickText("创建交接待办"); await waitFor("document.body.innerText.includes('面对面调研/人工记录')", "create form");
  await setLabel("人工来源说明", "Synthetic face-to-face meeting record"); await setLabel("标题", title);
  await setLabel("负责人 ID", actorId); await setLabel("截止时间", localDue); await setLabel("创建原因", "Synthetic browser acceptance");
  const fields = await evaluate(`(() => { const row=document.querySelector('.field-row'); const values=['response','document','Signed response'];
    if(!row)return false; [...row.querySelectorAll('input[type=text],input:not([type])')].slice(0,3).forEach((element,index)=>{ const descriptor=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element),'value');
      descriptor.set.call(element,values[index]); element.dispatchEvent(new Event('input',{bubbles:true})); }); return true; })()`);
  if (!fields) throw new Error("Requested input fields unavailable"); await submitVisibleForm();
  await waitFor(`document.body.innerText.includes(${JSON.stringify(title)}) || document.querySelector('[role=alert]')`, `created ${title}`);
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].map(item=>item.innerText)");
  if (alerts.length) throw new Error(`Create failed: ${JSON.stringify(alerts)}`);
  await waitFor("!document.body.innerText.includes('正在提交…')", `settled create ${title}`); }

try {
  const page = await target(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
  socket.addEventListener("message", ({ data }) => { const message = JSON.parse(data); if (message.method === "Network.requestWillBeSent"
      && message.params.request.url.includes("/handover-action-items")) observations.push({ request: message.params.request.url,
        method: message.params.request.method, body: message.params.request.postData });
    else if (message.method === "Network.responseReceived") {
    const response = message.params.response; if (response.url.includes("/api/")) observations.push({ url: response.url, status: response.status }); }
    else if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (!message.id || !pending.has(message.id)) return; const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result); });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(() => { const set=(selector,value)=>{const element=document.querySelector(selector); const descriptor=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element),'value');
    descriptor.set.call(element,value); element.dispatchEvent(new Event('input',{bubbles:true}));}; set('#login-username','Synthetic Handover Manager');
    set('#login-password','synthetic-handover-browser-password'); return true; })()`);
  await evaluate("document.querySelector('button[type=submit]').click()"); await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await clickText("我的项目"); await waitFor("document.body.innerText.includes('Synthetic Handover Browser')", "project list");
  await clickText("Synthetic Handover Browser"); await waitFor("document.body.innerText.includes('查看项目交接待办与验证状态')", "project detail");
  await clickText("查看项目交接待办与验证状态"); await waitFor("document.body.innerText.includes('交接待办与验证状态')", "action workbench");
  if (await evaluate("Boolean(document.querySelector('[role=alert]'))")) {
    await clickText("刷新交接待办"); await waitFor("!document.querySelector('[role=alert]') && document.body.innerText.includes('当前项目没有可见待办。')", "refreshed empty action list");
  }

  await createAction("Browser signed response"); await openAction("Browser signed response");
  await clickText("修改待办信息", "document.querySelector('.action-detail')"); await setLabel("标题", "Browser final signed response");
  await setLabel("优先级", "URGENT", "select"); await clickText("保存并重新读取", "document.querySelector('.action-detail')");
  await waitFor("document.body.innerText.includes('更新待办已受理，并已重新读取当前待办事实。')", "patched action");
  await clickText("开始处理", "document.querySelector('.action-detail')"); await setLabel("操作理由", "Synthetic work started"); await submitVisibleForm();
  await waitFor("document.body.innerText.includes('当前状态：处理中')", "started action");
  await clickText("提交响应", "document.querySelector('.action-detail')"); await setLabel("响应文档与固定版本", `${documentId}, ${versionId}`);
  await setLabel("Evidence ID", submissionId); await setLabel("操作理由", "Synthetic signed response submitted"); await submitVisibleForm();
  await waitFor("document.body.innerText.includes('当前状态：已提交待验证')", "submitted action");
  await clickText("验证响应", "document.querySelector('.action-detail')"); await setLabel("Evidence ID", verificationId);
  await setLabel("操作理由", "Synthetic response verified"); await submitVisibleForm();
  await waitFor("document.body.innerText.includes('当前状态：已验证待关闭') && document.body.innerText.includes('CR-HND-008')", "verified fail-closed action");
  const closeDisabled = await evaluate(`(() => { const button=[...document.querySelectorAll('button')].find(item=>item.textContent.includes('关闭待办'));
    return Boolean(button?.disabled); })()`); if (!closeDisabled) throw new Error("CLOSE was not fail-closed");
  const verifiedShot = await screenshot("01-verified-close-disabled.png");

  await createAction("Browser obsolete response"); await openAction("Browser obsolete response");
  await clickText("取消待办", "document.querySelector('.action-detail')"); await setLabel("操作理由", "Synthetic duplicate cancelled"); await submitVisibleForm();
  await waitFor("document.body.innerText.includes('当前状态：已取消')", "cancelled action");
  const cancelledShot = await screenshot("02-cancelled.png");
  const alerts = await evaluate("[...document.querySelectorAll('[role=alert]')].map(item=>item.innerText)");
  if (alerts.length) throw new Error(`Unexpected UI alerts: ${JSON.stringify(alerts)}`);
  const required = ["/handover-action-items", ":start", ":submit", ":verify", ":cancel"];
  const api = observations.filter(item => item.status >= 200 && item.status < 300);
  const missing = required.filter(part => !api.some(item => item.url.includes(part)));
  if (missing.length) throw new Error(`Missing successful API observations: ${JSON.stringify({ missing, observations })}`);
  console.log("HND_02_A05_A06_EDGE_BROWSER_PASS");
  console.log(JSON.stringify({ status: "PASS", screenshots: [verifiedShot, cancelledShot], apiResponses: api.length })); socket.close();
} catch (error) { console.error(JSON.stringify({ observations }, null, 2)); throw error;
} finally { processHandle.kill(); await pause(300); await rm(profile, { recursive: true, force: true }); }
