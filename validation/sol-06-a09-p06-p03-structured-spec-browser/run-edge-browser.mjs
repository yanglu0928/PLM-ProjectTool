/** Owned headless Edge proof of actual SOL-06 DRAFT creation and exact replay. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, section, _document, _documentVersion,
  requirement, requirementVersion, evidence] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const detailMode = process.env.PLM_SPEC_DETAIL_ACCEPTANCE === "1";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, section, requirement, requirementVersion,
    evidence].every(value => uuid.test(value ?? ""))
  || project === otherProject || typeof password !== "string" || password.length < 24) {
  throw new Error("owned synthetic inputs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-structured-spec-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "--window-size=1440,1000", "about:blank"],
  { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
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
const pending = new Map(); const responses = []; const requests = []; const errors = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, { resolve: resolveCall, reject: rejectCall }));
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
    "({url:location.href,text:document.body?.innerText?.slice(0,1800),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-12))}; errors=${JSON.stringify(errors.slice(-5))}`);
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
async function setValue(selector, value) {
  await evaluate(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});
    if(!input)throw new Error('Missing input '+${JSON.stringify(selector)});
    input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
}
const createPath = `/api/v1/projects/${project}/structured-solution-specs`;
const pagePath = `/projects/${project}/structured-solution-specs/new`;
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
      && event.params.request.url === `${origin}${createPath}`) {
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
  await setValue("#login-username", "Section Browser Writer");
  await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "login success");
  await route(pagePath);
  await waitFor(`document.querySelector('input[value="${section}"]')`, "current section candidate");
  for (const path of [`/projects/${project}/requirements?`,
    `/projects/${project}/solution-sections?`,
    `/projects/${project}/solution-sections/${section}/versions?`,
    `/projects/${project}/evidence?`]) {
    if (!responses.some(item => item.url.includes(`/api/v1${path}`) && item.status === 200)) {
      throw new Error(`Real candidate GET 200 missing: ${path}`);
    }
  }
  await evaluate(`(()=>{for(const identity of ${JSON.stringify([requirement, section, evidence])}){
    const item=[...document.querySelectorAll('input[type=checkbox]')].find(x=>x.value===identity);
    if(!item)throw new Error('Missing current source '+identity);item.click();}})()`);
  for (const [selector, value] of [
    ["#spec-source", "Old PLM"], ["#spec-target", "New PLM"],
    ["#spec-mappings", "old_id → part_id"], ["#spec-scope", "Parts"],
    ["#spec-cleansing", "Deduplicate"], ["#spec-trial", "Trial batch"],
    ["#spec-reconcile", "Compare by part number"], ["#spec-rollback", "Restore snapshot"],
    ["#spec-acceptance", "No differences"],
  ]) await setValue(selector, value);
  await evaluate("[...document.querySelectorAll('form input[type=checkbox]')].at(-1)?.click()");
  if (!await evaluate("document.querySelector('button[type=submit]')?.disabled===false")) {
    throw new Error("Synthetic draft submit not enabled");
  }
  await clickText("创建 DRAFT 草案");
  await waitFor("document.body?.innerText?.includes('专项草案已创建')", "created DRAFT");
  if (requests.length !== 1 || responses.filter(item => item.url === `${origin}${createPath}`
    && item.status === 201).length !== 1) throw new Error("First real CREATE 201 missing");
  const original = requests[0];
  const key = Object.entries(original.headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1];
  const body = JSON.parse(original.body);
  if (typeof key !== "string" || body.spec_type !== "MIGRATION_SPEC"
    || body.requirement_refs?.[0]?.requirement_version_id !== requirementVersion
    || body.section_refs?.[0]?.solution_section_id !== section
    || body.evidence_ids?.[0] !== evidence || body.artifact_ids?.length !== 0
    || body.payload?.scope !== "Parts") throw new Error("Browser original request mismatch");
  const actor = await evaluate(`(async()=>{const response=await fetch('/api/v1/auth/session',
    {credentials:'same-origin',cache:'no-store'});return (await response.json()).data.user.user_id})()`);
  if (!uuid.test(actor)) throw new Error("Current actor unavailable");
  await evaluate(`(()=>sessionStorage.setItem(${JSON.stringify(
    `plm.sol.spec.create.pending.${actor}.${project}`)},JSON.stringify(${JSON.stringify({
    project, actor, draft: body, key,
  })})))()`);
  await route(`/projects/${project}/solution-sections`);
  await waitFor("document.body?.innerText?.includes('方案章节')", "leave create page");
  await route(pagePath);
  await waitFor("document.body?.innerText?.includes('存在原创建操作')", "pending restore");
  if (await evaluate("document.querySelector('#spec-source')!==null")) {
    throw new Error("Pending operation allowed changed draft");
  }
  await evaluate("document.querySelector('form input[type=checkbox]').click()");
  await clickText("按原操作号重试");
  await waitFor("document.body?.innerText?.includes('专项草案已创建')", "replayed receipt");
  if (requests.length !== 2 || requests[1].body !== original.body
    || Object.entries(requests[1].headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1] !== key
    || responses.filter(item => item.url === `${origin}${createPath}` && item.status === 201).length !== 2) {
    throw new Error("Original-key replay changed request or did not return 201");
  }
  if (detailMode) {
    await clickText("查看专项详情");
    await waitFor("document.querySelector('#spec-detail-title')", "detail route");
    const specId = await evaluate("location.pathname.split('/').at(-1)");
    if (!uuid.test(specId)) throw new Error("Created detail link has no version identity");
    const detailPath = `/api/v1/projects/${project}/structured-solution-specs/${specId}`;
    await waitFor(`document.body?.innerText?.includes(${JSON.stringify(requirementVersion)}) &&
      document.body?.innerText?.includes('Old PLM')`, "fixed detail content");
    if (!responses.some(item => item.url === `${origin}${detailPath}` && item.status === 200)) {
      throw new Error("Real detail GET 200 missing");
    }
    const detail = await evaluate(`(()=>({text:document.body.innerText,
      requirement:document.querySelector('a[href*="/requirements/"]')?.getAttribute('href'),
      section:document.querySelector('a[href*="/solution-sections/"][href*="/versions/"]')?.getAttribute('href'),
      raw:document.querySelector('.spec-detail pre')!==null}))()`);
    if (!["数据迁移", "Parts", "old_id", "part_id", "固定来源引用", evidence,
      "尚无评审记录"].every(part => detail.text.includes(part))
      || !detail.requirement?.includes(`/projects/${project}/requirements/${requirement}`)
      || !detail.section?.includes(`/projects/${project}/solution-sections/${section}/versions/`)
      || detail.raw) throw new Error(`Detail projection or fixed links invalid: ${JSON.stringify(detail)}`);
    const crossPath = `/api/v1/projects/${otherProject}/structured-solution-specs/${specId}`;
    const directCrossStatus = await evaluate(`(async()=>{
      const response=await fetch(${JSON.stringify(crossPath)},
        {credentials:'same-origin',cache:'no-store'});return response.status})()`);
    if (directCrossStatus !== 404) throw new Error(`Cross-project detail returned ${directCrossStatus}`);
    await route(`/projects/${otherProject}/structured-solution-specs/${specId}`);
    await waitFor("document.body?.innerText?.includes('当前会话没有此项目的读取权限')",
      "cross-project detail denied");
    if (await evaluate("document.body.innerText.includes('Old PLM')")) {
      throw new Error("Cross-project detail retained previous content");
    }
    if (responses.some(item => item.url === `${origin}${crossPath}` && item.status === 200)) {
      throw new Error("Cross-project detail leaked HTTP 200");
    }
  }
  await route(`/projects/${otherProject}/structured-solution-specs/new`);
  await waitFor("document.body?.innerText?.includes('创建结构化专项草案')", "cross-project route");
  if (await evaluate("document.querySelector('form')!==null")) throw new Error("Cross-project create leaked");
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log(detailMode
    ? "STRUCTURED_SPEC_DETAIL_EDGE PASS: create/replay, real detail GET, fixed links, cross-project 404/hidden"
    : "STRUCTURED_SPEC_CREATE_EDGE PASS: current candidates, real DRAFT 201, original-key replay, cross-project hidden");
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill();
  await new Promise(resolveExit => edge.once("exit", resolveExit));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Browser profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
