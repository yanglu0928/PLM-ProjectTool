/** Disposable Edge proof of manager VALIDATE -> customer Section Review submit. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, section, version, customer] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const managerName = process.env.PLM_BROWSER_MANAGER_NAME;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, section, version, customer].every(v => uuid.test(v ?? ""))
  || project === otherProject || typeof password !== "string" || password.length < 24
  || !managerName) throw new Error("Owned synthetic browser inputs required");

const profile = await mkdtemp(join(tmpdir(), "plm-section-manager-edge-"));
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
      const page = targets.find(item => item.type === "page");
      if (page) return page;
    } catch { /* Owned Edge is starting. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}
let socket, serial = 0;
const pending = new Map(), responses = [], errors = [], submitRequests = [];
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, {
    resolve: resolveCall, reject: rejectCall,
  }));
}
async function evaluate(expression) {
  const answer = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (answer.exceptionDetails) throw new Error(`Browser exception: ${answer.exceptionDetails.text}`);
  return answer.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 240; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  const state = await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,1800),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})");
  throw new Error(`Timed out ${label}: ${JSON.stringify(state)}; responses=${JSON.stringify(responses.slice(-12))}; errors=${JSON.stringify(errors.slice(-5))}`);
}
async function clickText(label) {
  const clicked = await evaluate(`(()=>{const node=[...document.querySelectorAll('a,button')].find(x=>x.textContent.trim()===${JSON.stringify(label)});if(!node||node.disabled)return false;node.click();return true})()`);
  if (!clicked) throw new Error(`Missing or disabled action ${label}`);
}
function route(path) {
  return evaluate(`(()=>{history.pushState(null,'',${JSON.stringify(path)});dispatchEvent(new PopStateEvent('popstate'))})()`);
}
async function setValue(selector, value) {
  await evaluate(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});if(!input)throw new Error('Missing input');input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}))})()`);
}

const detailPath = `/projects/${project}/solution-sections/${section}/versions/${version}`;
const validatePath = `/api/v1/projects/${project}/solution-sections/${section}/versions/${version}:validate`;
const submitPath = `/api/v1/projects/${project}/solution-sections/${section}/versions/${version}:submit-review`;
try {
  const page = await findPage(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((ok, bad) => {
    socket.addEventListener("open", ok, { once: true });
    socket.addEventListener("error", bad, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text);
    if (event.method === "Network.requestWillBeSent" && event.params.request.url === `${origin}${submitPath}`) {
      submitRequests.push({ headers: event.params.request.headers, body: event.params.request.postData });
    }
    if (event.method === "Network.responseReceived" && event.params.response.url.includes("/api/")) {
      responses.push({ url: event.params.response.url, status: event.params.response.status });
    }
    if (!event.id || !pending.has(event.id)) return;
    const task = pending.get(event.id); pending.delete(event.id);
    event.error ? task.reject(new Error(event.error.message)) : task.resolve(event.result);
  });
  await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
  const edgeVersion = await send("Browser.getVersion");
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", managerName);
  await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "manager login");
  await route(detailPath);
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='验证当前来源'&&!x.disabled)", "Section validation form");
  await waitFor(`document.body?.innerText?.includes('请先验证当前固定章节并达到送审条件')`, "Section submit gated before proof");
  if (await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='提交客户章节评审')")) {
    throw new Error("Submit visible before readiness validation");
  }
  await clickText("验证当前来源");
  await waitFor("document.body?.innerText?.includes('验证条件满足；仍需正式评审与客户确认')", "six-dimension ready report");
  await waitFor(`[...document.querySelectorAll('.section-review input[type=checkbox]')].some(x=>x.value===${JSON.stringify(customer)})`, "qualified customer candidate");
  if (!responses.some(x => x.url === `${origin}${validatePath}` && x.status === 200)) {
    throw new Error("Real Section VALIDATE request missing");
  }
  if (!await evaluate(`(()=>{const input=[...document.querySelectorAll('.section-review input[type=checkbox]')].find(x=>x.value===${JSON.stringify(customer)});if(!input)return false;input.click();return true})()`)) {
    throw new Error("Qualified customer checkbox missing");
  }
  await clickText("提交客户章节评审");
  await waitFor("document.body?.innerText?.includes('已送审，评审')", "Section Review receipt");
  if (submitRequests.length !== 1
    || !responses.some(x => x.url === `${origin}${submitPath}` && x.status === 201)
    || JSON.stringify(JSON.parse(submitRequests[0].body)) !== JSON.stringify({
      reviewer_ids: [customer], policy_ref: "SOLUTION_SECTION_ALL_V1",
      due_at: null, submission_note: null,
    })) throw new Error("Section submit body/201 mismatch");
  const headers = submitRequests[0].headers;
  const key = Object.entries(headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1];
  const csrf = Object.entries(headers).find(([name]) => name.toLowerCase() === "x-csrf-token")?.[1];
  if (typeof key !== "string" || key.length < 16 || typeof csrf !== "string") {
    throw new Error("Section submit idempotency/CSRF missing");
  }
  const replay = await evaluate(`(async()=>{const response=await fetch(${JSON.stringify(submitPath)},
    {method:'POST',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json',
      'Content-Type':'application/json','Idempotency-Key':${JSON.stringify(key)},
      'X-CSRF-Token':${JSON.stringify(csrf)}},body:${JSON.stringify(submitRequests[0].body)}});
    return {status:response.status,body:await response.json()}})()`);
  if (replay.status !== 201 || replay.body?.data?.state !== "IN_REVIEW"
    || replay.body?.data?.solution_section_version_id !== version
    || submitRequests.length !== 2) {
    throw new Error(`Section same-key replay failed: ${JSON.stringify(replay)}`);
  }
  await clickText("打开评审");
  await waitFor("document.body?.innerText?.includes('查看本轮固定章节版本')", "manager Review reread");
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  if (typeof screenshot.data !== "string" || screenshot.data.length < 1000 || errors.length) {
    throw new Error(`Edge render/exception failure: ${JSON.stringify(errors)}`);
  }
  console.log(`SECTION_MANAGER_EDGE PASS: ${edgeVersion.product}; validate, select customer, submit, 201 replay, Review reread, PNG bytes=${Math.floor(screenshot.data.length * 3 / 4)}`);
} finally {
  try { socket?.close(); } catch { /* Owned Edge shuts down below. */ }
  edge.kill(); await new Promise(done => edge.once("exit", done));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Edge profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
