/** Owned headless Edge proof over disposable profile and synthetic loopback PG. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, documentId, versionId, evidenceId, password, mode] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![documentId, versionId, evidenceId].every(value => uuid.test(value ?? ""))
  || password !== "Synthetic-Reference-Browser-Only-2026"
  || (mode !== undefined && mode !== "create")) throw new Error("synthetic owned arguments required");
const profile = await mkdtemp(join(tmpdir(), "plm-attestation-edge-"));
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
    } catch { /* Owned Edge not listening yet. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket; let serial = 0; let confirmKey; let createKey; let createBody;
const pending = new Map(); const responses = []; const browserErrors = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolvePromise, reject) => pending.set(id, { resolvePromise, reject }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser exception: ${result.exceptionDetails.text}`);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 150; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,2000),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent),buttons:[...document.querySelectorAll('button')].map(x=>({text:x.textContent,disabled:x.disabled}))})"))}; responses=${JSON.stringify(responses.slice(-12))}; browserErrors=${JSON.stringify(browserErrors.slice(-8))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});if(!item)return false;item.click();return true})()`)) {
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
    if (event.method === "Runtime.exceptionThrown") browserErrors.push(event.params.exceptionDetails?.text);
    if (event.method === "Runtime.consoleAPICalled" && event.params.type === "error") {
      browserErrors.push(event.params.args?.map(item => item.value ?? item.description).join(" "));
    }
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (event.method === "Network.requestWillBeSent") {
      const item = event.params.request;
      if (item.method === "POST" && item.url.endsWith("/api/v1/global/reference-deidentification-confirmations")) {
        confirmKey = item.headers["Idempotency-Key"] ?? item.headers["idempotency-key"];
      }
      if (item.method === "POST" && item.url.endsWith("/api/v1/global/reference-solutions")) {
        createKey = item.headers["Idempotency-Key"] ?? item.headers["idempotency-key"];
        createBody = JSON.parse(item.postData);
      }
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolvePromise(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.body?.innerText?.includes('登录项目实施辅助工具')", "login shell");
  await evaluate(`(()=>{const username=document.querySelector('#login-username');
    const password=document.querySelector('#login-password');
    username.value='Reference Admin';username.dispatchEvent(new Event('input',{bubbles:true}));
    password.value=${JSON.stringify(password)};password.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "real admin login");
  await clickText("全局证据");
  await waitFor("document.body?.innerText?.includes('Synthetic Reference')", "GLOBAL Evidence list");
  await clickText("定位固定原文");
  await waitFor("document.body?.innerText?.includes('已核验的全局证据')", "GLOBAL Evidence selected");
  await clickText("对这条固定来源进行人工脱敏核查");
  await waitFor("document.body?.innerText?.includes('当前固定来源')", "current GLOBAL Evidence Viewer");
  const link = await evaluate("document.querySelector('a[href*=" + JSON.stringify(`/versions/${versionId}/content`) + "]')?.getAttribute('href')");
  // The fixed content URL appears after preview, so the initial page must not yet expose a claim.
  if (link) throw new Error("Unpreviewed original link shown as reviewed");
  await evaluate(`(()=>{const inputs=[...document.querySelectorAll('input:not([type=checkbox])')];
    inputs[0].value='PLM';inputs[0].dispatchEvent(new Event('input',{bubbles:true}));
    inputs[1].value='DEIDENTIFIED';inputs[1].dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await waitFor(`[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='预览当前固定来源'&&!item.disabled)`, "preview enabled after classification input");
  await clickText("预览当前固定来源");
  await waitFor("document.body?.innerText?.includes('预览时刻')", "current source preview");
  const hrefs = await evaluate(`[...document.querySelectorAll('a[href*="/content"]')]
    .map(item=>item.getAttribute('href'))`);
  if (hrefs.length !== 2 || hrefs.some(item => item !==
      `/api/v1/global/documents/${documentId}/versions/${versionId}/content`)) {
    throw new Error("Fixed GLOBAL document links did not bind current version");
  }
  if (await evaluate(`!document.querySelector('button')`)) throw new Error("Missing action buttons");
  await evaluate(`(()=>{const links=[...document.querySelectorAll('a[href*="/content"]')];
    links.forEach(item=>item.click());return true})()`);
  await evaluate(`(()=>{[...document.querySelectorAll('input[type=checkbox]')]
    .forEach(item=>item.click());return true})()`);
  await waitFor(`[...document.querySelectorAll('button')].some(item=>item.textContent.includes('提交人工脱敏确认')&&!item.disabled)`, "human confirmation enabled");
  await clickText("提交人工脱敏确认（有效期 7 天）");
  await waitFor("document.body?.innerText?.includes('确认号')", "confirmed attestation");
  if (!/^[\x20-\x7e]{16,128}$/.test(confirmKey ?? "")) throw new Error("Original confirm operation key not captured");
  if (mode === "create") {
    if (!await evaluate(`(()=>{const item=document.querySelector('input[placeholder="填写便于识别的参考名称"]');
      if(!item)return false;item.value='Synthetic single-source reference';
      item.dispatchEvent(new Event('input',{bubbles:true}));return true})()`)) {
      throw new Error("Reference name input unavailable");
    }
    await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='重新核验并创建全局参考方案'&&!x.disabled)", "GLOBAL Create ready");
    await clickText("重新核验并创建全局参考方案");
    await waitFor("document.body?.innerText?.includes('全局参考方案已创建为仅供参考的草稿')", "GLOBAL Reference created");
    if (!/^[\x20-\x7e]{16,128}$/.test(createKey ?? "")
      || createBody.name !== "Synthetic single-source reference"
      || JSON.stringify(createBody.document_version_ids) !== JSON.stringify([versionId])
      || JSON.stringify(createBody.evidence_ids) !== JSON.stringify([evidenceId])
      || Object.keys(createBody).length !== 6
      || !responses.some(item => item.url.endsWith("/api/v1/global/reference-solutions")
        && item.status === 201)) throw new Error("GLOBAL Create source/body/201 failed");
  }
  await clickText("撤回此确认");
  await waitFor("document.body?.innerText?.includes('确认已撤回')", "revoked attestation");
  const actor = await evaluate("document.querySelector('body')?.dataset?.actor ?? ''");
  // Read current actor from the same authorized Session endpoint, not from page text.
  const principal = await evaluate(`(async()=>{const r=await fetch('/api/v1/auth/session',{credentials:'same-origin'});
    const p=await r.json();return p.data.user.user_id})()`);
  if (!uuid.test(principal) || actor && actor !== principal) throw new Error("Current admin identity mismatch");
  await evaluate(`sessionStorage.setItem(${JSON.stringify(`plm.sol.global.deidentification.pending.${principal}`)},
    JSON.stringify({actor:${JSON.stringify(principal)},evidence_id:${JSON.stringify(evidenceId)},
      kind:'confirm',key:${JSON.stringify(confirmKey)}}))`);
  await clickText("账户与登录");
  await waitFor("document.body?.innerText?.includes('读取当前身份')", "session page after synthetic pending");
  await evaluate("history.back()");
  await waitFor("document.body?.innerText?.includes('上次确认结果尚待核对')", "pending lock restored");
  await waitFor("[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='按原操作号回查'&&!item.disabled)", "pending lookup enabled after source load");
  await clickText("按原操作号回查");
  await waitFor("document.body?.innerText?.includes('首次操作已完成')", "receipt recovered");
  if (!await evaluate("document.body?.innerText?.includes('REVOKED')")) throw new Error("Current revoked state not shown");
  await evaluate(`(()=>{document.querySelector('[aria-label="待核对操作"] input[type=checkbox]').click();return true})()`);
  await clickText("清除本地待核对提醒");
  await waitFor("!document.body?.innerText?.includes('上次确认结果尚待核对')", "pending lock cleared after receipt");
  await send("Network.deleteCookies", { name: "plm_session", url: origin });
  await send("Page.reload", { ignoreCache: true });
  await waitFor("document.body?.innerText?.includes('需要当前 DeploymentAdmin')", "Session removed");
  for (const [path, status] of [["/api/v1/auth/session", 200],
    [`/api/v1/global/evidence/${evidenceId}/viewer`, 200],
    ["/api/v1/global/reference-deidentification-confirmations:preview", 200],
    ["/api/v1/global/reference-deidentification-confirmations", 201],
    ["/api/v1/global/reference-deidentification-confirmations:lookup-operation", 200]]) {
    if (!responses.some(item => item.url.includes(path) && item.status === status)) {
      throw new Error(`Expected real API response absent ${path} ${status}`);
    }
  }
  console.log("GLOBAL_ATTESTATION_EDGE_PASS: Session, Viewer, fixed content links, preview/confirm/revoke, original-key recovery, logout");
} finally {
  socket?.close(); edge.kill();
  const tempRoot = resolve(tmpdir()) + sep;
  const resolved = resolve(profile);
  if (resolved.startsWith(tempRoot) && resolved.split(sep).at(-1)?.startsWith("plm-attestation-edge-")) {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try { await rm(resolved, { recursive: true, force: true }); break; }
      catch { await pause(200); }
    }
  }
}
