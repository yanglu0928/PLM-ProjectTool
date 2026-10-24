/** Owned headless Edge proof of SectionVersion CREATE page and original-key replay. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, section, document, documentVersion,
  requirement, requirementVersion, evidence] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, section, document, documentVersion, requirement,
    requirementVersion, evidence].every(value => uuid.test(value ?? ""))
  || project === otherProject || typeof password !== "string" || password.length < 24) {
  throw new Error("owned synthetic inputs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-section-create-page-edge-"));
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
const responses = []; const requests = []; const errors = [];
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
const createPath = `/api/v1/projects/${project}/solution-sections/${section}/versions`;
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
  await evaluate(`(()=>{const username=document.querySelector('#login-username');
    const secret=document.querySelector('#login-password');
    username.value='Section Browser Writer';username.dispatchEvent(new Event('input',{bubbles:true}));
    secret.value=${JSON.stringify(password)};secret.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "login success");
  await route(`/projects/${project}/solution-sections/${section}`);
  await waitFor("document.body?.innerText?.includes('创建章节草案版本')", "section create entry");
  await clickText("创建章节草案版本");
  await waitFor("document.querySelector('#section-version-document option[value=\"" + document + "\"]')", "document candidate");
  await evaluate(`(()=>{const input=document.querySelector('#section-version-title');
    input.value='Browser section draft';input.dispatchEvent(new Event('input',{bubbles:true}));
    const select=document.querySelector('#section-version-document');select.value=${JSON.stringify(document)};
    select.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await waitFor(`document.querySelector('#section-version-document-version option[value="${documentVersion}"]')`,
    "document version candidate");
  for (const path of [`/projects/${project}/documents?`,
    `/projects/${project}/documents/${document}/versions?`,
    `/projects/${project}/requirements?`, `/projects/${project}/evidence?`]) {
    if (!responses.some(item => item.url.includes(`/api/v1${path}`) && item.status === 200)) {
      throw new Error(`Real candidate GET 200 missing: ${path}`);
    }
  }
  await evaluate(`(()=>{const select=document.querySelector('#section-version-document-version');
    select.value=${JSON.stringify(documentVersion)};select.dispatchEvent(new Event('change',{bubbles:true}));
    for(const identity of ${JSON.stringify([requirement, evidence])}){
      const item=[...document.querySelectorAll('input[type=checkbox]')].find(x=>x.value===identity);
      if(!item)throw new Error('Missing current source '+identity);item.click();
    }
    const checks=[...document.querySelectorAll('input[type=checkbox]')];checks.at(-1).click();})()`);
  await clickText("创建 DRAFT 草案");
  await waitFor("document.body?.innerText?.includes('草案版本已创建')", "created version");
  const firstVersionLink = await evaluate("[...document.querySelectorAll('a')]"
    + ".find(x=>x.textContent.trim()==='查看固定版本详情')?.getAttribute('href')");
  if (!firstVersionLink || !uuid.test(firstVersionLink.split("/").at(-1))) {
    throw new Error("Created version detail link missing");
  }
  if (requests.length !== 1 || responses.filter(item => item.url === `${origin}${createPath}`
    && item.status === 201).length !== 1) throw new Error("First real CREATE 201 missing");
  const original = requests[0];
  const key = Object.entries(original.headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1];
  const body = JSON.parse(original.body);
  if (typeof key !== "string" || !body || body.title !== "Browser section draft"
    || body.content_document_version_ref !== documentVersion
    || body.requirement_refs?.[0]?.requirement_version_id !== requirementVersion
    || body.evidence_ids?.[0] !== evidence) throw new Error("Browser original request mismatch");
  const actor = await evaluate(`(async()=>{const response=await fetch('/api/v1/auth/session',
    {credentials:'same-origin',cache:'no-store'});return (await response.json()).data.user.user_id})()`);
  if (!uuid.test(actor)) throw new Error("Current actor unavailable");
  await evaluate(`(()=>sessionStorage.setItem(${JSON.stringify(
    `plm.sol.section.version.create.pending.${actor}.${project}.${section}`)},JSON.stringify(${JSON.stringify({
    project, section, actor, draft: body, key,
  })})))()`);
  await route(`/projects/${project}/solution-sections/${section}`);
  await waitFor("document.body?.innerText?.includes('创建章节草案版本')", "return to section");
  await clickText("创建章节草案版本");
  await waitFor("document.body?.innerText?.includes('存在原创建操作')", "pending restore");
  if (await evaluate("document.querySelector('#section-version-title')!==null")) {
    throw new Error("Pending operation allowed changed draft");
  }
  await evaluate(`(()=>document.querySelector('form input[type=checkbox]').click())()`);
  await clickText("按原操作号重试");
  await waitFor("document.body?.innerText?.includes('草案版本已创建')", "replayed receipt");
  const replayVersionLink = await evaluate("[...document.querySelectorAll('a')]"
    + ".find(x=>x.textContent.trim()==='查看固定版本详情')?.getAttribute('href')");
  if (replayVersionLink !== firstVersionLink) throw new Error("Replay did not return original version");
  if (requests.length !== 2 || requests[1].body !== original.body
    || Object.entries(requests[1].headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1] !== key
    || responses.filter(item => item.url === `${origin}${createPath}` && item.status === 201).length !== 2) {
    throw new Error("Original-key replay changed request or did not return 201");
  }
  await route(`/projects/${otherProject}/solution-sections/${section}/versions/new`);
  await waitFor("document.body?.innerText?.includes('创建章节草案版本')", "cross-project route");
  if (await evaluate("document.querySelector('form')!==null")) throw new Error("Cross-project create leaked");
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log("SECTION_VERSION_CREATE_EDGE PASS: candidate GET, real CREATE 201, original-key replay 201, cross-project hidden");
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill();
  await new Promise(resolveExit => edge.once("exit", resolveExit));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Browser profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
