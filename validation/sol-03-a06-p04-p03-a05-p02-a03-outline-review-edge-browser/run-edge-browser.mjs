/** Owned Edge proof: manager SOL-03 submit then independent customer approval. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, outline, version, customer] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const managerName = process.env.PLM_BROWSER_MANAGER_NAME;
const customerName = process.env.PLM_BROWSER_CUSTOMER_NAME;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, outline, version, customer].every(v => uuid.test(v ?? ""))
  || project === otherProject || typeof password !== "string" || password.length < 24
  || !managerName || !customerName) throw new Error("Owned synthetic browser inputs required");

const profile = await mkdtemp(join(tmpdir(), "plm-outline-review-edge-"));
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
  const state = await evaluate("({url:location.href,text:document.body?.innerText?.slice(0,2200),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})");
  throw new Error(`Timed out ${label}: ${JSON.stringify(state)}; responses=${JSON.stringify(responses.slice(-15))}; errors=${JSON.stringify(errors.slice(-5))}`);
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
async function login(name) {
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", name);
  await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "account login");
}

const detailPath = `/projects/${project}/solution-outlines/${outline}/versions/${version}`;
const submitPath = `/api/v1/projects/${project}/solution-outlines/${outline}/versions/${version}:submit-review`;
const listApi = `${origin}/api/v1/projects/${project}/reviews`;
let review, round;
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
  await login(managerName);
  await route(detailPath);
  await waitFor(`[...document.querySelectorAll('.outline-review input[type=checkbox]')].some(x=>x.value===${JSON.stringify(customer)})`, "customer reviewer candidate");
  if (!await evaluate(`(()=>{const input=[...document.querySelectorAll('.outline-review input[type=checkbox]')].find(x=>x.value===${JSON.stringify(customer)});if(!input)return false;input.click();return true})()`)) {
    throw new Error("Customer checkbox missing");
  }
  await evaluate("(()=>{const label=[...document.querySelectorAll('.outline-review label')].find(x=>x.textContent.includes('我已核对本固定方案大纲版本'));const input=label?.querySelector('input');if(!input)throw new Error('scope confirmation missing');input.click()})()");
  await clickText("提交客户方案大纲评审");
  await waitFor("document.body?.innerText?.includes('已送审，评审')", "Outline submit receipt");
  if (submitRequests.length !== 1
    || !responses.some(x => x.url === `${origin}${submitPath}` && x.status === 201)
    || JSON.stringify(JSON.parse(submitRequests[0].body)) !== JSON.stringify({
      reviewer_ids: [customer], policy_ref: "SOLUTION_OUTLINE_ALL_V1",
      due_at: null, submission_note: null,
    })) throw new Error("Outline submit body/201 mismatch");
  const reviewPath = await evaluate("document.querySelector('.outline-review a[href*=" +
    "\"/reviews/\"]')?.getAttribute('href')");
  review = reviewPath?.split("/").at(-1);
  if (!uuid.test(review ?? "")) throw new Error("Review receipt link missing");
  await clickText("打开评审");
  await waitFor("document.body?.innerText?.includes('查看本轮固定大纲版本')", "manager Review reread");

  await send("Network.clearBrowserCookies");
  await login(customerName);
  await route(`/projects/${project}/reviews`);
  await waitFor(`document.body?.innerText?.includes(${JSON.stringify(review)})&&document.body.innerText.includes('评审中 · 方案大纲')`, "customer pending Outline");
  if (!responses.some(x => x.url.startsWith(`${listApi}?view=my_pending`) && x.status === 200)) {
    throw new Error("Customer pending Review was not discovered by server");
  }
  await clickText("打开评审并核对当前状态");
  await waitFor("document.body?.innerText?.includes('查看本轮固定大纲版本')", "customer Review detail");
  const fixed = `/projects/${project}/solution-outlines/${outline}/versions/${version}`;
  if (!await evaluate(`Boolean(document.querySelector('a[href=${JSON.stringify(fixed)}]'))`)) {
    throw new Error("Fixed OutlineVersion link missing");
  }
  await clickText("查看本轮固定大纲版本");
  await waitFor(`location.pathname===${JSON.stringify(fixed)}&&document.body?.innerText?.includes('方案固定版本详情')`, "customer fixed OutlineVersion");
  await route(`/projects/${project}/reviews/${review}`);
  await waitFor("document.body?.innerText?.includes('查看本轮固定大纲版本')", "customer Review return");
  await evaluate("(()=>{const label=[...document.querySelectorAll('.review label')].find(x=>x.textContent.includes('我已核对固定方案大纲版本'));const input=label?.querySelector('input');if(!input)throw new Error('approval confirmation missing');input.click()})()");
  await clickText("批准本轮");
  await waitFor("document.body?.innerText?.includes('决定已记录：批准')&&document.body.innerText.includes('当前没有活动轮次')", "terminal approval");
  if (!responses.some(x => x.url.includes(`/api/v1/projects/${project}/reviews/${review}/rounds/`) && x.status === 200)) {
    throw new Error("Review decision HTTP 200 missing");
  }
  await clickText("返回评审待办与历史");
  await waitFor("document.body?.innerText?.includes('当前没有待处理评审')", "pending removed");
  await clickText("全部可见历史");
  await waitFor(`document.body?.innerText?.includes(${JSON.stringify(review)})&&document.body.innerText.includes('已批准')`, "terminal history");
  await route(`/projects/${otherProject}/reviews`);
  await waitFor("document.body?.innerText?.includes('当前会话没有此项目的读取权限')", "cross-project clear");
  if (await evaluate(`document.body.innerText.includes(${JSON.stringify(review)})`)) {
    throw new Error("Cross-project page retained Review content");
  }
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  if (typeof screenshot.data !== "string" || screenshot.data.length < 1000 || errors.length) {
    throw new Error(`Edge render/exception failure: ${JSON.stringify(errors)}`);
  }
  console.log(`SOL03_OUTLINE_EDGE PASS: ${edgeVersion.product}; manager submit 201, customer pending/fixed version/approval 200/history, cross-project clear, PNG bytes=${Math.floor(screenshot.data.length * 3 / 4)}`);
} finally {
  try { socket?.close(); } catch { /* Owned Edge shuts down below. */ }
  edge.kill(); await new Promise(done => edge.once("exit", done));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Edge profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
