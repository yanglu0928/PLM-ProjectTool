/** Owned headless Edge proof: current GLOBAL candidate -> fixed DRAFT reference. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, outline, section, reference, version, password] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, outline, section, reference, version].every(value => uuid.test(value ?? ""))
  || project === otherProject || password !== "Synthetic-Global-Candidate-Browser-Only-2026") {
  throw new Error("owned synthetic inputs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-global-candidate-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1000", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = targets.find(target => target.type === "page");
      if (page) return page;
    } catch { /* Browser not ready. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket; let serial = 0;
const pending = new Map(); const responses = []; const errors = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 180; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,1800),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-16))}; errors=${JSON.stringify(errors.slice(-5))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});
    if(!item||item.disabled)return false;item.click();return true})()`)) {
    throw new Error(`Missing or disabled action ${label}`);
  }
}
try {
  const page = await findPage();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolveOpen, rejectOpen) => {
    socket.addEventListener("open", resolveOpen, { once: true });
    socket.addEventListener("error", rejectOpen, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text);
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolve(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(()=>{const username=document.querySelector('#login-username');
    const secret=document.querySelector('#login-password');
    username.value='Reference Admin';username.dispatchEvent(new Event('input',{bubbles:true}));
    secret.value=${JSON.stringify(password)};secret.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "login success");
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(
    `/projects/${project}/solution-outlines/${outline}/versions/new`)});
    dispatchEvent(new PopStateEvent('popstate'));})()`);
  await waitFor("document.body?.innerText?.includes('审定的合成标签')", "GLOBAL candidate visible");
  if (!await evaluate("document.querySelectorAll('form fieldset').length===4")) {
    throw new Error("Four scoped candidate groups unavailable");
  }
  if (await evaluate("document.body?.innerText?.includes('Synthetic unreviewed raw name')")) {
    throw new Error("Admin raw name leaked to project page");
  }
  if (!await evaluate(`(()=>{const fields=document.querySelectorAll('form fieldset');
    const section=fields[0]?.querySelector('input[value=${JSON.stringify(section)}]');
    const global=fields[3]?.querySelector('input[value=${JSON.stringify(reference)}]');
    const confirm=document.querySelector('form > label input[type=checkbox]');
    if(!section||!global||!confirm)return false;section.click();global.click();confirm.click();return true})()`)) {
    throw new Error("Expected fixed section/GLOBAL selections unavailable");
  }
  await clickText("创建 DRAFT 草案");
  await waitFor("document.body?.innerText?.includes('草案版本已创建')", "DRAFT creation");
  if (!responses.some(item => item.url.includes(`/projects/${project}/global-reference-candidates`)
    && item.status === 200)) throw new Error("Project candidate GET 200 absent");
  if (!responses.some(item => item.url.includes(`/projects/${project}/solution-outlines/${outline}/versions`)
    && item.status === 201)) throw new Error("OutlineVersion POST 201 absent");
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(
    `/projects/${otherProject}/solution-outlines/${outline}/versions/new`)});
    dispatchEvent(new PopStateEvent('popstate'));})()`);
  await waitFor("document.body?.innerText?.includes('仅当前项目负责人或实施成员可创建')", "cross-project deny");
  if (await evaluate("document.body?.innerText?.includes('审定的合成标签')")) {
    throw new Error("GLOBAL candidate leaked into unauthorized project route");
  }
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log(`GLOBAL_CANDIDATE_EDGE PASS: ${project} DRAFT fixed GLOBAL ${reference}/${version}, cross-project hidden`);
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill();
  await new Promise(resolveExit => edge.once("exit", resolveExit));
  const safe = resolve(profile).startsWith(resolve(tmpdir()) + sep);
  if (!safe) throw new Error("Browser profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
