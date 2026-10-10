/** Owned Edge proof of two ordered GLOBAL Document/Evidence sources. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, documentA, versionA, evidenceA, password,
  documentB, versionB, evidenceB, mode] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![documentA, versionA, evidenceA, documentB, versionB, evidenceB]
    .every(value => uuid.test(value ?? ""))
  || documentA === documentB || versionA === versionB || evidenceA === evidenceB
  || password !== "Synthetic-Reference-Browser-Only-2026"
  || (mode !== undefined && mode !== "create" && mode !== "create-read")) {
  throw new Error("two distinct owned synthetic sources required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-multisource-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1900", "about:blank"],
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
let socket; let serial = 0; let confirmKey; let confirmBody; let createKey; let createBody;
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
    "({url:location.href,text:document.body?.innerText?.slice(0,2500),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent),buttons:[...document.querySelectorAll('button')].map(x=>({text:x.textContent,disabled:x.disabled}))})"))}; responses=${JSON.stringify(responses.slice(-15))}; errors=${JSON.stringify(browserErrors.slice(-8))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});if(!item||item.disabled)return false;item.click();return true})()`)) {
    throw new Error(`Missing or disabled browser action ${label}`);
  }
}
async function choose(label) {
  const chosen = await evaluate(`(()=>{const item=[...document.querySelectorAll('ol[aria-label="可选全局证据"] li')]
    .find(node=>node.textContent.includes(${JSON.stringify(label)}));
    const button=item?.querySelector('button');if(!button||button.disabled)return false;
    button.click();return true})()`);
  if (!chosen) throw new Error(`Missing selectable source ${label}`);
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
        confirmBody = JSON.parse(item.postData);
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
  await waitFor("document.body?.innerText?.includes('选择多条来源作为核查候选')", "GLOBAL Evidence entry");
  await clickText("选择多条来源作为核查候选");
  await waitFor("document.body?.innerText?.includes('Synthetic Second Reference')", "GLOBAL source picker");
  await choose("Synthetic Second Reference");
  await waitFor("document.body?.innerText?.includes('1 条证据')", "second source selected");
  await choose("Synthetic Reference");
  await waitFor("document.body?.innerText?.includes('2 条证据、2 个固定文档版本')", "two distinct sources selected");
  await evaluate(`(()=>{const inputs=[...document.querySelectorAll('input:not([type=checkbox])')];
    inputs[0].value='PLM';inputs[0].dispatchEvent(new Event('input',{bubbles:true}));
    inputs[1].value='DEIDENTIFIED';inputs[1].dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='预览所选来源集合'&&!x.disabled)", "preview ready");
  await clickText("预览所选来源集合");
  await waitFor("document.body?.innerText?.includes('预览时刻')", "ordered multi-source preview");
  const links = await evaluate(`[...document.querySelectorAll('section[aria-label="集合预览与逐项原文核查"] a')]
    .map(x=>x.getAttribute('href'))`);
  const firstUrl = `/api/v1/global/documents/${documentA}/versions/${versionA}/content`;
  const secondUrl = `/api/v1/global/documents/${documentB}/versions/${versionB}/content`;
  if (links.length !== 4 || links[0] !== secondUrl || links[1] !== firstUrl
    || links[2] !== secondUrl || links[3] !== firstUrl) {
    throw new Error(`Multi-source fixed links are not ordered/bound: ${JSON.stringify(links)}`);
  }
  if (await evaluate(`[...document.querySelectorAll('button')].find(x=>x.textContent.includes('提交集合人工脱敏确认'))?.disabled !== true`)) {
    throw new Error("Human confirmation enabled without opening/checking every source");
  }
  await evaluate(`(()=>{const section=document.querySelector('section[aria-label="集合预览与逐项原文核查"]');
    [...section.querySelectorAll('a')].forEach(x=>x.click());return true})()`);
  await waitFor("[...document.querySelectorAll('section[aria-label=\"集合预览与逐项原文核查\"] input[type=checkbox]')].every(x=>!x.disabled)", "source checkboxes enabled after opening");
  const checkCount = await evaluate(`document.querySelectorAll('section[aria-label="集合预览与逐项原文核查"] input[type=checkbox]').length`);
  if (checkCount !== 5) throw new Error(`Expected two documents, two Evidence and one declaration: ${checkCount}`);
  for (let index = 0; index < checkCount; index += 1) {
    await evaluate(`document.querySelectorAll('section[aria-label="集合预览与逐项原文核查"] input[type=checkbox]')[${index}].click()`);
    await waitFor(`document.querySelectorAll('section[aria-label="集合预览与逐项原文核查"] input[type=checkbox]')[${index}].checked`, `source check ${index}`);
  }
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='提交集合人工脱敏确认（有效期 7 天）'&&!x.disabled)", "all sources reviewed");
  await clickText("提交集合人工脱敏确认（有效期 7 天）");
  await waitFor("document.body?.innerText?.includes('集合人工确认已提交')", "multi-source confirmation");
  if (!/^[\x20-\x7e]{16,128}$/.test(confirmKey ?? "")
    || JSON.stringify(confirmBody.document_version_ids) !== JSON.stringify([versionB, versionA])
    || JSON.stringify(confirmBody.evidence_ids) !== JSON.stringify([evidenceB, evidenceA])) {
    throw new Error("Confirm did not preserve original Key and two-source order");
  }
  if (mode === "create" || mode === "create-read") {
    if (!await evaluate(`(()=>{const item=document.querySelector('input[placeholder="填写便于识别的参考名称"]');
      if(!item)return false;item.value='Synthetic multi-source reference';
      item.dispatchEvent(new Event('input',{bubbles:true}));return true})()`)) {
      throw new Error("Reference name input unavailable");
    }
    await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='重新核验并创建全局参考方案'&&!x.disabled)", "GLOBAL Create ready");
    await clickText("重新核验并创建全局参考方案");
    await waitFor("document.body?.innerText?.includes('全局参考方案已创建为仅供参考的草稿')", "GLOBAL Reference created");
    if (!/^[\x20-\x7e]{16,128}$/.test(createKey ?? "")
      || createBody.name !== "Synthetic multi-source reference"
      || JSON.stringify(createBody.document_version_ids) !== JSON.stringify([versionB, versionA])
      || JSON.stringify(createBody.evidence_ids) !== JSON.stringify([evidenceB, evidenceA])
      || Object.keys(createBody).length !== 6
      || !responses.some(item => item.url.endsWith("/api/v1/global/reference-solutions")
        && item.status === 201)) throw new Error("GLOBAL Create order/body/201 failed");
    if (mode === "create-read") {
      await clickText("打开刚创建的参考方案详情");
      await waitFor("document.body?.innerText?.includes('全局参考方案详情与固定来源')", "created reference detail");
      await waitFor("document.body?.innerText?.includes('Synthetic multi-source reference')", "read created GLOBAL Reference");
      const identity = await evaluate("location.pathname.split('/').at(-1)");
      if (!uuid.test(identity)) throw new Error("Created Reference identity is not canonical");
      const fixed = await evaluate(`(()=>{const doc=[...document.querySelectorAll('a')]
        .filter(x=>x.textContent.includes('打开固定文档版本原文'));
        return doc.map(x=>x.getAttribute('href'))})()`);
      if (JSON.stringify(fixed) !== JSON.stringify([
        `/api/v1/global/documents/${documentB}/versions/${versionB}/content`,
        `/api/v1/global/documents/${documentA}/versions/${versionA}/content`])) {
        throw new Error(`Created Reference lost ordered document links: ${JSON.stringify(fixed)}`);
      }
      const fixedDownload = await evaluate(`(async()=>{const link=[...document.querySelectorAll('a')]
        .find(x=>x.textContent.includes('打开固定文档版本原文'));
        const response=await fetch(link.getAttribute('href'),{credentials:'same-origin'});
        return {status:response.status,bytes:(await response.arrayBuffer()).byteLength}})()`);
      if (fixedDownload.status !== 200 || fixedDownload.bytes < 1) {
        throw new Error(`Authorized fixed document download failed: ${JSON.stringify(fixedDownload)}`);
      }
      await clickText("核验并定位原文");
      await waitFor("Boolean(document.querySelector('[aria-label=\"受权固定证据定位\"]'))", "GLOBAL Evidence viewer");
      const evidenceLink = await evaluate(`document.querySelector('[aria-label="受权固定证据定位"] a')?.getAttribute('href')`);
      if (!evidenceLink?.startsWith('/api/v1/global/documents/') || !evidenceLink.includes('/content')) {
        throw new Error(`Authorized GLOBAL Evidence content link missing: ${evidenceLink}`);
      }
      await clickText("返回全局参考方案候选");
      await waitFor("location.pathname==='/admin/reference-solutions' && [...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='读取候选')", "GLOBAL candidate page");
      await clickText("读取候选");
      await waitFor("document.body?.innerText?.includes('Synthetic multi-source reference')", "GLOBAL candidate list");
      const candidate = await evaluate(`document.querySelector('a[href="/admin/reference-solutions/${identity}"]')?.textContent`);
      if (!candidate?.includes('固定来源')) throw new Error("Created GLOBAL candidate navigation missing");
      for (const [path, status] of [
        [`/api/v1/global/reference-solutions/${identity}`, 200],
        ['/api/v1/global/reference-solutions?page_size=50', 200],
        [`/api/v1/global/documents/${documentB}/versions/${versionB}/content`, 200],
        [`/api/v1/global/evidence/${evidenceB}/viewer`, 200],
      ]) if (!responses.some(item => item.url.includes(path) && item.status === status)) {
        throw new Error(`Expected real GLOBAL read missing: ${path} ${status}`);
      }
      await clickText("查看固定来源与待核对信息");
      await waitFor(`location.pathname==='/admin/reference-solutions/${identity}'`, "candidate detail return");
      await send("Network.deleteCookies", { name: "plm_session", url: origin });
      await clickText("重新读取详情");
      await waitFor("document.body?.innerText?.includes('会话已失效')", "GLOBAL read after Session removal");
      if (await evaluate(`Boolean(document.querySelector('a[href*="/versions/"][href*="/content"]'))`)) {
        throw new Error("Historical content link remained after Session removal");
      }
      if (!responses.some(item => item.url.includes(`/api/v1/global/reference-solutions/${identity}`)
        && item.status === 401)) throw new Error("GLOBAL detail 401 after Session removal missing");
    }
  }
  if (mode !== "create-read") {
  await clickText("撤回此集合确认");
  await waitFor("document.body?.innerText?.includes('集合确认已撤回')", "multi-source revoke");
  const principal = await evaluate(`(async()=>{const response=await fetch('/api/v1/auth/session',{credentials:'same-origin'});
    const payload=await response.json();return payload.data.user.user_id})()`);
  if (!uuid.test(principal)) throw new Error("Current admin identity unavailable");
  await evaluate(`sessionStorage.setItem(${JSON.stringify(`plm.sol.global.deidentification.multi.pending.${principal}`)},
    JSON.stringify({actor:${JSON.stringify(principal)},kind:'confirm',key:${JSON.stringify(confirmKey)}}))`);
  await clickText("账户与登录");
  await waitFor("document.body?.innerText?.includes('读取当前身份')", "session page after pending");
  await evaluate("history.back()");
  await waitFor("document.body?.innerText?.includes('上次确认结果尚待核对')", "pending lock restored");
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='按原操作号回查'&&!x.disabled)", "lookup ready");
  await clickText("按原操作号回查");
  await waitFor("document.body?.innerText?.includes('首次操作已完成')", "original receipt recovered");
  if (!await evaluate("document.body?.innerText?.includes('REVOKED')")) throw new Error("Current revoked state absent");
  await evaluate(`(()=>{document.querySelector('section[aria-label="待核对集合操作"] input[type=checkbox]').click();return true})()`);
  await clickText("清除本地待核对提醒");
  await waitFor("!document.body?.innerText?.includes('上次确认结果尚待核对')", "pending cleared after review");
  await send("Network.deleteCookies", { name: "plm_session", url: origin });
  await send("Page.reload", { ignoreCache: true });
  await waitFor("location.pathname==='/login'||document.body?.innerText?.includes('需要当前 DeploymentAdmin')", "Session removed");
  for (const [path, status] of [["/api/v1/auth/login", 200],
    ["/api/v1/global/reference-deidentification-confirmations:preview", 200],
    ["/api/v1/global/reference-deidentification-confirmations", 201],
    ["/api/v1/global/reference-deidentification-confirmations:lookup-operation", 200]]) {
    if (!responses.some(item => item.url.endsWith(path) && item.status === status)) {
      throw new Error(`Expected real API response absent ${path} ${status}`);
    }
  }
  console.log("GLOBAL_MULTISOURCE_EDGE_PASS: ordered two Document/Evidence sources, review, confirm/revoke, original-key recovery");
  } else {
    console.log("GLOBAL_REFERENCE_READ_EDGE_PASS: Create→GET/List, fixed document download, Evidence Viewer, Session removal");
  }
} finally {
  socket?.close(); edge.kill();
  const tempRoot = resolve(tmpdir()) + sep;
  const resolved = resolve(profile);
  if (resolved.startsWith(tempRoot) && resolved.split(sep).at(-1)?.startsWith("plm-multisource-edge-")) {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try { await rm(resolved, { recursive: true, force: true }); break; }
      catch { await pause(200); }
    }
  }
}
