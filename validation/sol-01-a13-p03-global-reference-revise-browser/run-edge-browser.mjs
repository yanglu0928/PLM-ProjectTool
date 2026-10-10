/** Owned Edge proof: GLOBAL create, new human confirmation, lost revision 201 and same-key recovery. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, documentA, versionA, evidenceA, password,
  documentB, versionB, evidenceB] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![documentA, versionA, evidenceA, documentB, versionB, evidenceB].every(value => uuid.test(value ?? ""))
  || password !== "Synthetic-Reference-Browser-Only-2026") throw new Error("Owned fixture required");
const profile = await mkdtemp(join(tmpdir(), "plm-global-revise-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1900", "about:blank"],
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
let socket; let serial = 0; let lostFirst = false; let reference;
const pending = new Map(); const posts = []; const responses = []; const errors = []; const paused = [];
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
    "({url:location.href,text:document.body?.innerText?.slice(0,2600),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-12))}; errors=${JSON.stringify(errors.slice(-5))}`);
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
async function choose(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('ol[aria-label="可选全局证据"] li')]
    .find(node=>node.textContent.includes(${JSON.stringify(label)}));
    const action=item?.querySelector('button');if(!action||action.disabled)return false;
    action.click();return true})()`)) throw new Error(`Source unavailable ${label}`);
}
async function reviewAndConfirm() {
  await clickText("预览所选来源集合");
  await waitFor("document.body?.innerText?.includes('预览时刻')", "source preview");
  if (!await evaluate("[...document.querySelectorAll('section[aria-label=\"集合预览与逐项原文核查\"] a')].length===4")) {
    throw new Error("Expected two fixed Document and Evidence links");
  }
  if (!await evaluate("[...document.querySelectorAll('button')].find(x=>x.textContent.includes('提交集合人工脱敏确认'))?.disabled")) {
    throw new Error("Human confirmation enabled before review");
  }
  await evaluate(`(()=>{document.querySelectorAll('section[aria-label="集合预览与逐项原文核查"] a')
    .forEach(x=>x.click());})()`);
  await waitFor("[...document.querySelectorAll('section[aria-label=\"集合预览与逐项原文核查\"] input[type=checkbox]')].every(x=>!x.disabled)", "review links opened");
  for (let index = 0; index < 5; index += 1) {
    await evaluate(`document.querySelectorAll('section[aria-label="集合预览与逐项原文核查"] input[type=checkbox]')[${index}].click()`);
  }
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='提交集合人工脱敏确认（有效期 7 天）'&&!x.disabled)", "review completed");
  await clickText("提交集合人工脱敏确认（有效期 7 天）");
  await waitFor("document.body?.innerText?.includes('集合人工确认已提交')", "human confirmation");
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
      && reference && event.params.request.url.endsWith(`/api/v1/global/reference-solutions/${reference}:revise`)) {
      const item = event.params.request;
      posts.push({ key: item.headers["Idempotency-Key"] ?? item.headers["idempotency-key"],
        ifMatch: item.headers["If-Match"] ?? item.headers["if-match"], body: item.postData });
    }
    if (event.method === "Fetch.requestPaused") {
      const { requestId, request, responseStatusCode } = event.params;
      const revise = reference && request.method === "POST"
        && request.url.endsWith(`/api/v1/global/reference-solutions/${reference}:revise`);
      if (revise) paused.push({ status: responseStatusCode, url: request.url });
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
  await loginAt("/admin/reference-deidentification", "Reference Admin");
  await waitFor("document.body?.innerText?.includes('Synthetic Second Reference')", "create sources");
  await choose("Synthetic Second Reference");
  await waitFor("document.body?.innerText?.includes('1 条证据')", "first selected");
  await choose("Synthetic Reference");
  await waitFor("document.body?.innerText?.includes('2 条证据、2 个固定文档版本')", "initial sources");
  await setInput('input[placeholder="PLM"]', "PLM");
  await setInput('input[placeholder="DEIDENTIFIED"]', "DEIDENTIFIED");
  await reviewAndConfirm();
  await setInput('input[placeholder="填写便于识别的参考名称"]', "Synthetic GLOBAL revise root");
  await clickText("重新核验并创建全局参考方案");
  await waitFor("document.body?.innerText?.includes('全局参考方案已创建为仅供参考的草稿')", "root created");
  await clickText("打开刚创建的参考方案详情");
  await waitFor("document.body?.innerText?.includes('全局参考方案详情与固定来源')", "root detail");
  reference = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(reference)) throw new Error("Reference root ID unavailable");
  await clickText("修订此全局参考方案（新建草稿版本）");
  await waitFor("document.body?.innerText?.includes('修订全局参考方案')", "revision route");
  await waitFor("document.body?.innerText?.includes('Synthetic Second Reference')", "revision sources");
  if (!await evaluate("document.body?.innerText?.includes('当前 ETag')")) throw new Error("Current ETag absent");
  await choose("Synthetic Reference");
  await waitFor("document.body?.innerText?.includes('1 条证据')", "revised first source");
  await choose("Synthetic Second Reference");
  await waitFor("document.body?.innerText?.includes('2 条证据、2 个固定文档版本')", "revised second source");
  await setInput('input[placeholder="DEIDENTIFIED"]', "REDACTED");
  await reviewAndConfirm();
  await send("Fetch.enable", { patterns: [{ urlPattern: `*${reference}:revise`, requestStage: "Response" }] });
  await clickText("重新核验并修订为新草稿版本");
  await waitFor("document.body?.innerText?.includes('修订结果待核对')", "lost 201 locked");
  for (let n = 0; n < 100 && !lostFirst; n += 1) await pause(100);
  if (!lostFirst || posts.length !== 1) throw new Error(`First 201 not intercepted: lost=${lostFirst} paused=${JSON.stringify(paused)} posts=${JSON.stringify(posts)} reviseResponses=${JSON.stringify(responses.filter(x=>x.url.includes(':revise')))} page=${JSON.stringify(await evaluate("document.body?.innerText?.slice(-600)"))}`);
  const pendingKey = await evaluate(`Object.keys(sessionStorage).find(x=>x.includes('.reference.revise.pending.'))`);
  if (!pendingKey) throw new Error("Original revise operation not saved");
  await loginAt(`/admin/reference-solutions/${reference}/revise`, "Reference Admin");
  await waitFor("document.body?.innerText?.includes('原请求同号重试')", "pending restored");
  if (await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='重新核验并修订为新草稿版本'&&!x.disabled)")) {
    throw new Error("New revise remained enabled");
  }
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='原请求同号重试'&&!x.disabled)", "original operation available");
  await clickText("原请求同号重试");
  await waitFor("document.body?.innerText?.includes('当前详情已确认指向该版本')", "current version refreshed");
  if (posts.length !== 2 || posts[0].key !== posts[1].key
    || posts[0].ifMatch !== posts[1].ifMatch || posts[0].body !== posts[1].body
    || await evaluate(`Boolean(sessionStorage.getItem(${JSON.stringify(pendingKey)}))`)) {
    throw new Error("Recovery did not preserve original request or clear pending");
  }
  await loginAt(`/admin/reference-solutions/${reference}`, "Reference Reader");
  await waitFor("document.body?.innerText?.includes('当前账户无权查看全局参考方案')", "reader denied detail");
  if (await evaluate("document.body?.innerText?.includes('修订此全局参考方案')")) {
    throw new Error("Non-admin revision entry visible");
  }
  await loginAt(`/admin/reference-solutions/${reference}/revise`, "Reference Reader");
  await waitFor("document.body?.innerText?.includes('需要当前 DeploymentAdmin')", "reader denied revise UI");
  const outsiderLogin = await fetch(`${origin}/api/v1/auth/login`, {
    method: "POST", headers: { Origin: origin, Accept: "application/json",
      "Content-Type": "application/json" },
    body: JSON.stringify({ username: "Reference Reader", password }),
  });
  const outsiderData = await outsiderLogin.json();
  const outsiderCookie = outsiderLogin.headers.get("set-cookie")?.split(";")[0];
  if (outsiderLogin.status !== 200 || !outsiderCookie || !outsiderData.data?.csrf_token) {
    throw new Error("Non-admin synthetic HTTP Session unavailable");
  }
  const denied = await fetch(`${origin}/api/v1/global/reference-solutions/${reference}:revise`, {
    method: "POST", headers: { Origin: origin, Cookie: outsiderCookie,
      Accept: "application/json", "Content-Type": "application/json",
      "X-CSRF-Token": outsiderData.data.csrf_token,
      "If-Match": '"v1"', "Idempotency-Key": "non-admin-revise-denied-0001" },
    body: posts[0].body,
  });
  if (denied.status !== 404) throw new Error(`Non-admin direct revision not denied: ${denied.status}`);
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log("GLOBAL_REFERENCE_REVISE_EDGE PASS: create, fresh confirmation, lost201/same-key, current GET, non-admin denied");
} finally {
  try { socket?.close(); } catch { /* Owned cleanup. */ }
  edge.kill();
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Unsafe owned profile path");
  if (edge.exitCode === null && edge.signalCode === null) {
    await Promise.race([new Promise(resolvePromise => edge.once("exit", resolvePromise)), pause(3000)]);
  }
  await pause(500);
  await rm(profile, { recursive: true, force: true, maxRetries: 15, retryDelay: 200 });
}
