/** Owned headless Edge proof of audited SectionVersion VALIDATE page. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, section, _document, _documentVersion,
  _requirement, _requirementVersion, _evidence, version] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, section, version].every(value => uuid.test(value ?? ""))
  || project === otherProject || typeof password !== "string" || password.length < 24) {
  throw new Error("owned synthetic inputs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-section-validate-page-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,1000", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
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
let socket; let serial = 0; const pending = new Map();
const requests = []; const responses = []; const errors = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, {
    resolve: resolveCall, reject: rejectCall,
  }));
}
async function evaluate(expression) {
  const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(`Browser exception: ${response.exceptionDetails.text}`);
  return response.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 180; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,1600),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-10))}; errors=${JSON.stringify(errors.slice(-5))}`);
}
async function clickText(label) {
  if (!await evaluate(`(()=>{const item=[...document.querySelectorAll('a,button')]
    .find(node=>node.textContent.trim()===${JSON.stringify(label)});
    if(!item||item.disabled)return false;item.click();return true})()`)) {
    throw new Error(`Missing or disabled action ${label}`);
  }
}
function route(path) {
  return evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(path)});
    dispatchEvent(new PopStateEvent('popstate'));})()`);
}
const validatePath = `/api/v1/projects/${project}/solution-sections/${section}/versions/${version}:validate`;
const detailPath = `/projects/${project}/solution-sections/${section}/versions/${version}`;
try {
  const page = await findPage();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((opened, failed) => {
    socket.addEventListener("open", opened, { once: true });
    socket.addEventListener("error", failed, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text);
    if (event.method === "Network.requestWillBeSent"
      && event.params.request.url === `${origin}${validatePath}`) {
      requests.push({ headers: event.params.request.headers, body: event.params.request.postData });
    }
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
    username.value='Section Browser Writer';username.dispatchEvent(new Event('input',{bubbles:true}));
    secret.value=${JSON.stringify(password)};secret.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "login success");
  await route(detailPath);
  await waitFor("document.body?.innerText?.includes('验证当前来源')", "validate action");
  await waitFor("document.body?.innerText?.includes('SectionVersion') || document.body?.innerText?.includes('章节固定版本详情')", "detail page");
  await clickText("验证当前来源");
  await waitFor("document.querySelector('.validation-report')", "audited report");
  const firstReport = await evaluate("document.querySelector('.validation-report')?.innerText");
  if (!firstReport.includes("固定内容与来源核验通过")
    || !firstReport.includes("追溯覆盖：暂无法核验")
    || !firstReport.includes("结构化规格：暂无法核验")
    || !firstReport.includes("尚不具备送审条件")) throw new Error("Six-dimension report misleading");
  const firstAudit = await evaluate("document.querySelector('.validation-report code')?.textContent");
  if (!uuid.test(firstAudit ?? "")) throw new Error("Audited report id missing");
  if (requests.length !== 1 || requests[0].body
    || responses.filter(item => item.url === `${origin}${validatePath}` && item.status === 200).length !== 1) {
    throw new Error("First real bodyless VALIDATE 200 missing");
  }
  const key = Object.entries(requests[0].headers)
    .find(([name]) => name.toLowerCase() === "idempotency-key")?.[1];
  if (typeof key !== "string" || key.length < 16) throw new Error("Original validation key missing");
  const actor = await evaluate(`(async()=>{const response=await fetch('/api/v1/auth/session',
    {credentials:'same-origin',cache:'no-store'});return (await response.json()).data.user.user_id})()`);
  if (!uuid.test(actor)) throw new Error("Current actor unavailable");
  await evaluate(`(()=>sessionStorage.setItem(${JSON.stringify(
    `plm.sol.section.version.validate.pending.${actor}.${project}.${section}.${version}`)},JSON.stringify(${JSON.stringify({
    actor, project, section, version, key,
  })})))()`);
  await route(`/projects/${project}/solution-sections/${section}`);
  await waitFor("document.body?.innerText?.includes('章节详情')", "return to section");
  await route(detailPath);
  await waitFor("document.body?.innerText?.includes('存在未确认的原验证操作')", "pending restore");
  if (await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='验证当前来源')")) {
    throw new Error("Pending operation allowed a fresh validation key");
  }
  await evaluate("(()=>document.querySelector('input[type=checkbox]').click())()");
  await clickText("按原操作号重试验证");
  await waitFor("document.querySelector('.validation-report')", "replayed report");
  const replayAudit = await evaluate("document.querySelector('.validation-report code')?.textContent");
  if (replayAudit !== firstAudit || requests.length !== 2
    || requests[1].body
    || Object.entries(requests[1].headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1] !== key
    || responses.filter(item => item.url === `${origin}${validatePath}` && item.status === 200).length !== 2) {
    throw new Error("Original-key replay changed first audit or sent a body");
  }
  await route(`/projects/${otherProject}/solution-sections/${section}/versions/${version}`);
  await waitFor("document.body?.innerText?.includes('章节固定版本详情')", "cross-project route");
  if (await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='验证当前来源')")) {
    throw new Error("Cross-project validation button leaked");
  }
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log("SECTION_VERSION_VALIDATE_EDGE PASS: real page click, six-dimension report, bodyless POST, original-key replay, cross-project hidden");
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill();
  await new Promise(resolveExit => edge.once("exit", resolveExit));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Browser profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
