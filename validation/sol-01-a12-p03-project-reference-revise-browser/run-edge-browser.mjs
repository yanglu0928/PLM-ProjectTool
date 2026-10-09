/** Owned headless Edge proof: PROJECT Reference revision lost 201/same-key recovery. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, reference, version, password] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, reference, version].every(value => uuid.test(value ?? ""))
  || !/^[A-Za-z0-9_-]{40,64}$/.test(password ?? "")) {
  throw new Error("Owned synthetic inputs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-reference-revise-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1200", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function findPage() {
  for (let n = 0; n < 100; n += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      const page = targets.find(target => target.type === "page");
      if (page) return page;
    } catch { /* Owned Edge not listening yet. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket; let serial = 0; let lostFirst = false;
const pending = new Map(); const posts = []; const responses = []; const errors = [];
function send(method, params = {}) {
  const id = ++serial; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolvePromise, reject) => pending.set(id, { resolvePromise, reject }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser script exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 180; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,2500),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-8))}; errors=${JSON.stringify(errors.slice(-5))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});
    if(!item||item.disabled)return false;item.click();return true})()`)) throw new Error(`Missing or disabled ${label}`);
}
async function check(selector) {
  if (!await evaluate(`(()=>{const item=document.querySelector(${JSON.stringify(selector)});
    if(!item||item.disabled)return false;item.click();return item.checked})()`)) throw new Error(`Checkbox unavailable ${selector}`);
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
try {
  const page = await findPage();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((ok, bad) => { socket.addEventListener("open", ok, { once: true });
    socket.addEventListener("error", bad, { once: true }); });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (event.method === "Network.requestWillBeSent" && event.params.request.method === "POST"
      && event.params.request.url.endsWith(`/api/v1/projects/${project}/reference-solutions/${reference}:revise`)) {
      const headers = event.params.request.headers;
      posts.push({ key: headers["Idempotency-Key"] ?? headers["idempotency-key"],
        ifMatch: headers["If-Match"] ?? headers["if-match"], body: event.params.request.postData });
    }
    if (event.method === "Fetch.requestPaused") {
      const { requestId, request, responseStatusCode } = event.params;
      const revise = request.method === "POST"
        && request.url.endsWith(`/api/v1/projects/${project}/reference-solutions/${reference}:revise`);
      if (revise && !lostFirst && responseStatusCode === 201) {
        lostFirst = true;
        void (async () => { try { await send("Fetch.failRequest", { requestId, errorReason: "Failed" });
          await send("Fetch.disable"); } catch (error) { errors.push(String(error)); } })();
      } else void send("Fetch.continueResponse", { requestId }).catch(error => errors.push(String(error)));
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolvePromise(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await loginAt(`/projects/${project}/reference-solutions/${reference}`, "Browser Reference Manager");
  await waitFor("document.body?.innerText?.includes('选择固定来源并修订草稿')", "manager detail entry");
  await clickText("选择固定来源并修订草稿");
  await waitFor("document.body?.innerText?.includes('修订项目参考方案')", "revise page");
  await clickText("读取项目文档候选");
  await waitFor("document.body?.innerText?.includes('Synthetic Interview')", "real document candidate");
  await clickText("查看可用版本");
  await waitFor("Boolean(document.querySelector('a[href*=versionId]'))", "available fixed version");
  const href = await evaluate("document.querySelector('a[href*=versionId]')?.getAttribute('href')");
  if (!href?.includes(`versionId=${version}`)) throw new Error(`Fixed DocumentVersion link missing: ${href}`);
  await clickText("选择此版本");
  await waitFor(`Boolean(document.querySelector('input[type=checkbox][value="${version}"]'))`, "chosen version");
  await check(`input[type=checkbox][value="${version}"]`);
  await check("section[aria-label='修订分类和确认'] input[type=checkbox]:last-of-type");
  await send("Fetch.enable", { patterns: [{ urlPattern: `*${reference}:revise`, requestStage: "Response" }] });
  await clickText("重新核验并修订");
  await waitFor("document.body?.innerText?.includes('上次修订结果待核对')", "lost 201 locked state");
  if (!lostFirst || posts.length !== 1 || !posts[0].key
    || !await evaluate("sessionStorage.length === 1")) throw new Error("First result/key not retained");
  await loginAt(`/projects/${project}/reference-solutions/${reference}/revise`, "Browser Reference Manager");
  await waitFor("document.body?.innerText?.includes('同键恢复原操作')", "restored pending operation");
  if (!await evaluate("[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='重新核验并修订')?.disabled")) {
    throw new Error("New operation was not locked");
  }
  await clickText("同键恢复原操作");
  await waitFor("document.body?.innerText?.includes('本次修订回执')", "same-key first result");
  await waitFor("document.body?.innerText?.includes('重新读取当前第 2 版')", "current root refreshed");
  if (posts.length !== 2 || posts[0].key !== posts[1].key
    || posts[0].ifMatch !== posts[1].ifMatch || posts[0].body !== posts[1].body
    || !await evaluate("sessionStorage.length === 0")) throw new Error("Retry changed original operation");
  await loginAt(`/projects/${project}/reference-solutions/${reference}`, "Browser Reference Customer");
  await waitFor("document.body?.innerText?.includes('参考方案详情与固定来源')", "customer detail");
  if (await evaluate("document.body?.innerText?.includes('选择固定来源并修订草稿')")) {
    throw new Error("Customer was shown revision entry");
  }
  await loginAt(`/projects/${project}/reference-solutions/${reference}/revise`, "Browser Reference Customer");
  await waitFor("document.body?.innerText?.includes('仅项目经理或实施成员可修订')", "customer write denied");
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log("PROJECT_REFERENCE_REVISE_EDGE PASS: real DocumentVersion, lost201/same-key, current GET, customer hidden/denied");
} finally {
  try { socket?.close(); } catch { /* Owned cleanup. */ }
  edge.kill();
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Unsafe owned profile cleanup path");
  if (edge.exitCode === null && edge.signalCode === null) {
    await Promise.race([new Promise(resolve => edge.once("exit", resolve)), pause(3000)]);
  }
  await pause(500);
  await rm(profile, { recursive: true, force: true, maxRetries: 15, retryDelay: 200 });
}
