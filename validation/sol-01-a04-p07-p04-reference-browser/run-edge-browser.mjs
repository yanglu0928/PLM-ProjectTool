/** Owned headless Edge proof; only synthetic loopback data and disposable profile. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, reference, version, evidence, sessionHex] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, reference, version, evidence].every(value => uuid.test(value ?? ""))
  || !/^[0-9a-f]{64}$/.test(sessionHex ?? "")) throw new Error("owned synthetic arguments required");
const profile = await mkdtemp(join(tmpdir(), "plm-reference-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1900", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = targets.find(target => target.type === "page");
      if (page) return page;
    } catch { /* Edge not listening yet. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket;
let serial = 0;
const pending = new Map();
const responses = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolvePromise, reject) => pending.set(id, { resolvePromise, reject }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser script exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 150; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,5000)})"))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const link=[...document.querySelectorAll('a,button')]
    .find(item=>item.textContent.trim()===${JSON.stringify(label)});if(!link)return false;link.click();return true})()`)) {
    throw new Error(`Missing browser action ${label}`);
  }
}
try {
  const page = await findPage();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((ok, bad) => {
    socket.addEventListener("open", ok, { once: true });
    socket.addEventListener("error", bad, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolvePromise(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await send("Network.setCookie", { name: "plm_session", value: sessionHex, url: origin,
    httpOnly: true, secure: false, sameSite: "Lax" });
  await send("Page.navigate", { url: `${origin}/projects/${project}/reference-solutions` });
  await waitFor("document.body?.innerText?.includes('参考方案候选')", "reference list shell");
  await clickText("账户与登录");
  await waitFor("document.body?.innerText?.includes('读取当前身份')", "session page");
  await clickText("读取当前身份");
  await waitFor("document.body?.innerText?.includes('已读取当前身份')", "real session restored");
  await evaluate("history.back()");
  await waitFor("document.body?.innerText?.includes('Project Reference')", "reference list with real PG row");
  await clickText("查看固定来源与待核对信息");
  await waitFor("document.body?.innerText?.includes('固定文档版本')", "reference detail");
  const documentHref = await evaluate(`document.querySelector('a[href*="versionId="]')?.getAttribute('href')`);
  if (!documentHref?.includes(`versionId=${version}`)) throw new Error("Fixed DocumentVersion link missing");
  await clickText("打开固定版本与原文下载");
  await waitFor("document.body?.innerText?.includes('下载已核验固定版本原文')", "authorized document version");
  await evaluate("history.back()");
  await waitFor("document.body?.innerText?.includes('固定证据定位')", "reference detail return");
  await clickText("核验并定位原文");
  await waitFor("document.body?.innerText?.includes('Synthetic Interview')", "authorized Evidence locator");
  const downloadHref = await evaluate(`document.querySelector('a[href*="/documents/"][href*="/content"]')?.getAttribute('href')`);
  if (!downloadHref?.startsWith(`/api/v1/projects/${project}/documents/`)
    || !downloadHref.includes(`/versions/${version}/content`)) {
    throw new Error("Authorized Evidence content link missing");
  }
  for (const path of [`/api/v1/auth/session`, `/api/v1/projects/${project}/reference-solutions`,
    `/api/v1/projects/${project}/reference-solutions/${reference}`,
    `/api/v1/projects/${project}/evidence/${evidence}/viewer`]) {
    if (!responses.some(item => item.url.includes(path) && item.status === 200)) {
      throw new Error(`Expected successful real API response missing: ${path}`);
    }
  }
  await send("Network.deleteCookies", { name: "plm_session", url: origin });
  await clickText("重新读取详情");
  await waitFor("document.body?.innerText?.includes('会话已失效')", "revoked browser Session");
  if (await evaluate(`Boolean(document.querySelector('a[href*="versionId="]'))`)) {
    throw new Error("Historical source link remained visible after Session revocation");
  }
  if (!responses.some(item => item.url.includes(`/api/v1/projects/${project}/reference-solutions/${reference}`)
    && item.status === 401)) throw new Error("Expected revoked Session 401 missing");
  console.log("REFERENCE_EDGE_PASS: current Session, list/detail, fixed DocumentVersion, Evidence Viewer, revoked Session");
} finally {
  socket?.close(); edge.kill();
  const tempRoot = resolve(tmpdir()) + sep;
  const resolved = resolve(profile);
  if (resolved.startsWith(tempRoot) && resolved.split(sep).at(-1)?.startsWith("plm-reference-edge-")) {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try { await rm(resolved, { recursive: true, force: true }); break; }
      catch { await pause(200); }
    }
  }
}
