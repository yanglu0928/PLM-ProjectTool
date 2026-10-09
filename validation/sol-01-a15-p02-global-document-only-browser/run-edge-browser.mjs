/** Owned Edge proof: GLOBAL Reference create/revise with one DocumentVersion and zero Evidence. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, document, version, evidence, password] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![document, version, evidence].every(value => uuid.test(value ?? ""))
  || password !== "Synthetic-Reference-Browser-Only-2026") throw new Error("Owned fixture required");
const profile = await mkdtemp(join(tmpdir(), "plm-global-document-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1800", "about:blank"],
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
    "({url:location.href,text:document.body?.innerText?.slice(0,2200),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-10))}`);
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
async function chooseDocument() {
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='读取全局文档候选'&&!x.disabled)", "document candidate action ready");
  await clickText("读取全局文档候选");
  await waitFor("Boolean(document.querySelector('section[aria-label=\"全局文档版本候选\"] ol li button:not([disabled])'))", "GLOBAL Document candidate");
  await clickText("查看可用版本");
  await waitFor(`Boolean(document.querySelector('a[href*="${version}"]'))`, "fixed DocumentVersion");
  await clickText("选择此固定版本");
  await waitFor("document.body?.innerText?.includes('0 条证据、1 个固定文档版本')", "document-only selection");
  const link = await evaluate(`document.querySelector('section[aria-label="全局文档版本候选"] a[href*="${version}"]')?.getAttribute('href')`);
  if (link !== `/api/v1/global/documents/${document}/versions/${version}/content`) {
    throw new Error(`Wrong fixed document link: ${link}`);
  }
}
async function reviewAndConfirm() {
  await clickText("预览所选来源集合");
  await waitFor("document.body?.innerText?.includes('预览时刻')", "document-only preview");
  const review = 'section[aria-label="集合预览与逐项原文核查"]';
  if (!await evaluate(`document.querySelectorAll('${review} a').length===1`)) {
    throw new Error("Document-only preview had Evidence link");
  }
  const downloaded = await evaluate(`(async()=>{const item=document.querySelector('${review} a');
    const response=await fetch(item.getAttribute('href'),{credentials:'same-origin'});
    return {status:response.status,bytes:(await response.arrayBuffer()).byteLength}})()`);
  if (downloaded.status !== 200 || downloaded.bytes < 1) throw new Error("Fixed source download failed");
  await evaluate(`document.querySelector('${review} a').click()`);
  await waitFor(`![...document.querySelectorAll('${review} input[type=checkbox]')].some(x=>x.disabled)`, "document reviewed");
  const count = await evaluate(`document.querySelectorAll('${review} input[type=checkbox]').length`);
  if (count !== 2) throw new Error(`Unexpected Evidence checkbox: ${count}`);
  await evaluate(`document.querySelectorAll('${review} input[type=checkbox]')[0].click()`);
  await evaluate(`document.querySelectorAll('${review} input[type=checkbox]')[1].click()`);
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='提交集合人工脱敏确认（有效期 7 天）'&&!x.disabled)", "confirmation enabled");
  await clickText("提交集合人工脱敏确认（有效期 7 天）");
  await waitFor("document.body?.innerText?.includes('集合人工确认已提交')", "confirmed document-only source");
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
      && /\/api\/v1\/global\/reference-solutions(?:\/[^/]+:revise)?$/.test(event.params.request.url)) {
      posts.push({ url: event.params.request.url, body: JSON.parse(event.params.request.postData) });
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolvePromise(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  await send("Page.navigate", { url: `${origin}/admin/reference-deidentification` });
  await waitFor("document.body?.innerText?.includes('账户与登录')", "app shell");
  await clickText("账户与登录");
  await waitFor("document.querySelector('#login-username')", "login form");
  await setInput("#login-username", "Reference Admin");
  await setInput("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "real admin login");
  await evaluate("history.back()");
  await waitFor("location.pathname==='/admin/reference-deidentification'", "source picker return");
  await chooseDocument();
  await setInput('input[placeholder="PLM"]', "PLM");
  await setInput('input[placeholder="DEIDENTIFIED"]', "DEIDENTIFIED");
  await reviewAndConfirm();
  await setInput('input[placeholder="填写便于识别的参考名称"]', "Synthetic Document only reference");
  await clickText("重新核验并创建全局参考方案");
  await waitFor("document.body?.innerText?.includes('全局参考方案已创建为仅供参考的草稿')", "document-only root created");
  await clickText("打开刚创建的参考方案详情");
  await waitFor("document.body?.innerText?.includes('全局参考方案详情与固定来源')", "root detail");
  const reference = await evaluate("location.pathname.split('/').at(-1)");
  if (!uuid.test(reference)) throw new Error("Created root identity unavailable");
  await clickText("修订此全局参考方案（新建草稿版本）");
  await waitFor("document.body?.innerText?.includes('修订全局参考方案')", "revision page");
  await chooseDocument();
  await setInput('input[placeholder="DEIDENTIFIED"]', "REDACTED");
  await reviewAndConfirm();
  await clickText("重新核验并修订为新草稿版本");
  await waitFor("document.body?.innerText?.includes('当前详情已确认指向该版本')", "document-only revision current");
  if (posts.length !== 2 || posts.some(item => JSON.stringify(item.body.document_version_ids) !== JSON.stringify([version])
    || JSON.stringify(item.body.evidence_ids) !== "[]")
    || !responses.some(item => item.url.endsWith(`/api/v1/global/reference-solutions/${reference}:revise`)
      && item.status === 201)) throw new Error(`Document-only writes failed: ${JSON.stringify(posts)}`);
  console.log("GLOBAL_DOCUMENT_ONLY_EDGE PASS: authorized fixed file, zero Evidence, two confirmations, create/revise/current GET");
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
