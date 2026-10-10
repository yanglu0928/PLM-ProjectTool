/** Owned Win11 Edge proof: PROJECT human decision, current reread and permission. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, reference, _version, password] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, reference].every(value => uuid.test(value ?? ""))
  || !/^[A-Za-z0-9_-]{40,64}$/.test(password ?? "")) throw new Error("Owned fixture required");
const profile = await mkdtemp(join(tmpdir(), "plm-reference-eligibility-project-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1200", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolvePromise => setTimeout(resolvePromise, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = targets.find(item => item.type === "page");
      if (page) return page;
    } catch { /* Owned Edge starting. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket; let serial = 0;
const pending = new Map(); const posts = []; const responses = [];
function send(method, params = {}) {
  const id = ++serial; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolvePromise, reject) => pending.set(id, { resolvePromise, reject }));
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
    "({url:location.href,text:document.body?.innerText?.slice(0,2400),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-8))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});
    if(!item||item.disabled)return false;item.click();return true})()`)) throw new Error(`Missing or disabled ${label}`);
}
async function setInput(selector, value) {
  await evaluate(`(()=>{const item=document.querySelector(${JSON.stringify(selector)});
    if(!item)throw new Error('input missing');item.value=${JSON.stringify(value)};
    item.dispatchEvent(new Event('input',{bubbles:true}));})()`);
}
async function loginAt(path, username) {
  await send("Page.navigate", { url: `${origin}${path}` });
  await waitFor("document.body?.innerText?.includes('账户与登录')", "app shell");
  await clickText("账户与登录");
  await waitFor("document.querySelector('#login-username')", "login form");
  await setInput("#login-username", username);
  await setInput("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "real login");
  await evaluate("history.back()");
  await waitFor(`location.pathname === ${JSON.stringify(path)}`, "route return");
}
async function decide(target, reason, expectedEtag) {
  await waitFor(`Boolean(document.querySelector('section[aria-label="参考方案人工资格决定"] input[value="${target}"]'))`, "decision form");
  await evaluate(`document.querySelector('section[aria-label="参考方案人工资格决定"] input[value="${target}"]').click()`);
  await setInput('section[aria-label="参考方案人工资格决定"] textarea', reason);
  await clickText("核对并进入确认");
  if (posts.length !== (expectedEtag === '"v0"' ? 0 : 1)) throw new Error("Wrote before second confirmation");
  await waitFor("document.body?.innerText?.includes('不可变资格事件和审计')", "confirmation summary");
  await clickText("确认提交资格决定");
  await waitFor(`document.body?.innerText?.includes('首次提交回执：${target}')`, "first receipt");
  await waitFor(`document.body?.innerText?.includes('当前标记') && document.body?.innerText?.includes(${JSON.stringify(reason)})`, "current reread");
  if (posts.at(-1)?.ifMatch !== expectedEtag || posts.at(-1)?.body.eligibility_state !== target
    || posts.at(-1)?.body.reason !== reason) throw new Error(`Wrong decision POST: ${JSON.stringify(posts)}`);
}
try {
  const page = await findPage(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((ok, bad) => { socket.addEventListener("open", ok, { once: true });
    socket.addEventListener("error", bad, { once: true }); });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/"))
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    if (event.method === "Network.requestWillBeSent" && event.params.request.method === "POST"
      && event.params.request.url.endsWith(`/api/v1/projects/${project}/reference-solutions/${reference}:set-eligibility`)) {
      const headers = event.params.request.headers;
      posts.push({ key: headers["Idempotency-Key"] ?? headers["idempotency-key"],
        ifMatch: headers["If-Match"] ?? headers["if-match"], body: JSON.parse(event.params.request.postData) });
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolvePromise(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  const path = `/projects/${project}/reference-solutions/${reference}`;
  await loginAt(path, "Browser Reference Manager");
  await decide("ELIGIBLE", "人工核对当前固定来源", '"v0"');
  await decide("RESTRICTED", "等待补充复核", '"v1"');
  if (posts.length !== 2 || posts.some(item => !item.key)
    || !responses.some(item => item.url.endsWith(`${reference}:set-eligibility`) && item.status === 200))
    throw new Error(`Decision responses missing: ${JSON.stringify(responses.slice(-8))}`);
  await loginAt(path, "Browser Reference Customer");
  await waitFor("document.body?.innerText?.includes('参考方案详情与固定来源')", "customer detail");
  if (await evaluate("Boolean(document.querySelector('section[aria-label=\"参考方案人工资格决定\"] textarea'))"))
    throw new Error("Customer was shown eligibility write form");
  console.log("PROJECT_REFERENCE_ELIGIBILITY_EDGE PASS: two decisions, confirmation, current GET, customer hidden");
} finally {
  try { socket?.close(); } catch { /* Owned cleanup. */ }
  edge.kill();
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Unsafe owned profile path");
  if (edge.exitCode === null && edge.signalCode === null)
    await Promise.race([new Promise(resolvePromise => edge.once("exit", resolvePromise)), pause(3000)]);
  await pause(500);
  await rm(profile, { recursive: true, force: true, maxRetries: 15, retryDelay: 200 });
}
