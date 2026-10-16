/** Owned headless Edge proof of real SectionVersion history navigation. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, section, password] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, section].every(value => uuid.test(value ?? ""))
  || project === otherProject
  || password !== "Synthetic-Section-History-Browser-Only-2026") {
  throw new Error("owned synthetic inputs required");
}

const profile = await mkdtemp(join(tmpdir(), "plm-section-history-edge-"));
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
    } catch { /* Browser not listening yet. */ }
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
    "({url:location.href,text:document.body?.innerText?.slice(0,1800),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-12))}; errors=${JSON.stringify(errors.slice(-5))}`);
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
    username.value='Section History Reader';username.dispatchEvent(new Event('input',{bubbles:true}));
    secret.value=${JSON.stringify(password)};secret.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "login success");
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(
    `/projects/${project}/solution-sections/${section}`)});
    dispatchEvent(new PopStateEvent('popstate'));})()`);
  await waitFor("document.body?.innerText?.includes('查看此章节的版本历史')", "section detail");
  await clickText("查看此章节的版本历史");
  await waitFor("document.body?.innerText?.includes('版本 5 · DRAFT')", "history list");
  if (!await evaluate("document.body?.innerText?.includes('历史来源不证明目前仍合格')")) {
    throw new Error("Historical-not-current warning absent");
  }
  await clickText("查看固定版本详情");
  await waitFor("document.body?.innerText?.includes('固定正文来源')", "fixed detail");
  if (!await evaluate("document.body?.innerText?.includes('历史固定引用')")) {
    throw new Error("Historical fixed-reference warning absent");
  }
  if (!await evaluate("document.body?.innerText?.includes('不能从固定 UUID 推断下载地址')")) {
    throw new Error("Unverified locator warning absent");
  }
  const version = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(version)) throw new Error("Invalid version detail route");
  await evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(
    `/projects/${otherProject}/solution-sections/${section}/versions`)});
    dispatchEvent(new PopStateEvent('popstate'));})()`);
  await waitFor("document.body?.innerText?.includes('章节版本历史')", "cross-project route");
  if (await evaluate("document.body?.innerText?.includes('版本 5 · DRAFT')")) {
    throw new Error("Cross-project version leaked in browser");
  }
  const apiPath = `/api/v1/projects/${project}/solution-sections/${section}/versions`;
  if (!responses.some(item => item.url.startsWith(`${origin}${apiPath}?`) && item.status === 200)
    || !responses.some(item => item.url === `${origin}${apiPath}/${version}` && item.status === 200)) {
    throw new Error("Real list and detail HTTP 200 not both observed");
  }
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log(`SECTION_VERSION_EDGE PASS: member list/detail ${version}, fixed refs, cross-project hidden`);
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill();
  await new Promise(resolveExit => edge.once("exit", resolveExit));
  const safe = resolve(profile).startsWith(resolve(tmpdir()) + sep);
  if (!safe) throw new Error("Browser profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
