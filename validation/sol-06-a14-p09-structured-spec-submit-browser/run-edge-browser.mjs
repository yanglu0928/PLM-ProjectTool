/** Owned headless Edge proof of actual SOL-06 validation and submit-review UI. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, spec, series, reviewer] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const managerName = process.env.PLM_BROWSER_MANAGER_NAME;
const memberName = process.env.PLM_BROWSER_MEMBER_NAME;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, spec, series, reviewer].every(value => uuid.test(value ?? ""))
  || project === otherProject || typeof password !== "string" || password.length < 24
  || !managerName || !memberName) throw new Error("owned synthetic inputs required");

const profile = await mkdtemp(join(tmpdir(), "plm-structured-submit-edge-"));
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
    } catch { /* Edge is starting. */ }
    await pause(100);
  }
  throw new Error("Owned Edge target unavailable");
}

let socket; let serial = 0;
const pending = new Map(); const responses = []; const submitRequests = [];
const validateRequests = []; const errors = [];
function send(method, params = {}) {
  const id = ++serial; socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id,
    { resolve: resolveCall, reject: rejectCall }));
}
async function evaluate(expression) {
  const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(`Browser exception: ${response.exceptionDetails.text}`);
  return response.result.value;
}
async function waitFor(expression, label) {
  for (let n = 0; n < 240; n += 1) {
    try { if (await evaluate(`Boolean(${expression})`)) return; }
    catch (error) { if (!String(error).includes("Execution context was destroyed")) throw error; }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,2400),alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"))}; responses=${JSON.stringify(responses.slice(-16))}; errors=${JSON.stringify(errors.slice(-5))}`);
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
async function login(username) {
  await route("/login"); await waitFor("document.querySelector('#login-username')", "login form");
  await setValue("#login-username", username); await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", `${username} login`);
}

const detailPath = `/projects/${project}/structured-solution-specs/${spec}`;
const validatePath = `/api/v1/projects/${project}/structured-solution-specs/${spec}:validate`;
const submitPath = `/api/v1/projects/${project}/structured-solution-specs/${spec}:submit-review`;
try {
  const page = await findPage(); socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((opened, failed) => {
    socket.addEventListener("open", opened, { once: true });
    socket.addEventListener("error", failed, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails?.text);
    if (event.method === "Network.requestWillBeSent" && event.params.request.url === `${origin}${validatePath}`) {
      validateRequests.push({ headers: event.params.request.headers, body: event.params.request.postData });
    }
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
  const version = await send("Browser.getVersion");
  await send("Page.navigate", { url: `${origin}/login` });
  await waitFor("document.querySelector('#login-username')", "initial login form");

  await setValue("#login-username", memberName); await setValue("#login-password", password);
  await clickText("登录 / 重新登录");
  await waitFor("document.body?.innerText?.includes('登录成功')", "member login");
  await route(detailPath);
  await waitFor("document.body?.innerText?.includes('仅当前项目负责人可送审')", "member permissions");
  if (await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='提交正式评审')")) {
    throw new Error("ImplementationMember saw submit-review action");
  }

  await login(managerName); await route(detailPath);
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='验证当前事实'&&!x.disabled)",
    "manager detail ready");
  await clickText("验证当前事实");
  await waitFor("document.body?.innerText?.includes('当前检查满足送审前置')", "ready validation");
  if (validateRequests.length !== 1 || validateRequests[0].body !== undefined
    || responses.filter(item => item.url === `${origin}${validatePath}` && item.status === 200).length !== 1) {
    throw new Error("Real ready validation request missing");
  }
  if (!await evaluate(`(()=>{const input=[...document.querySelectorAll('.reviewers input[type=checkbox]')]
    .find(item=>item.value===${JSON.stringify(reviewer)});if(!input)return false;input.click();return true})()`)
    || !await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='提交正式评审'&&!x.disabled)")) {
    throw new Error("Active reviewer selection did not enable submit");
  }

  const actor = await evaluate(`(async()=>{const response=await fetch('/api/v1/auth/session',
    {credentials:'same-origin',cache:'no-store'});return (await response.json()).data.user.user_id})()`);
  if (!uuid.test(actor)) throw new Error("Current manager actor unavailable");
  const key = "structured-spec-review-edge-0001";
  const storageKey = `plm.sol.structured-spec.submit.pending.${actor}.${project}.${spec}`;
  const attempt = { actor, project, spec, series, reviewer_ids: [reviewer], key };
  await evaluate(`sessionStorage.setItem(${JSON.stringify(storageKey)},${JSON.stringify(JSON.stringify(attempt))})`);
  await route("/login"); await waitFor("document.querySelector('#login-username')", "leave detail");
  await route(detailPath);
  await waitFor("document.body?.innerText?.includes('存在结果未知的原送审操作')", "pending submission restore");
  if (await evaluate("document.querySelector('.reviewers')!==null")) {
    throw new Error("Pending submission allowed reviewer changes");
  }
  await evaluate(`(()=>{const label=[...document.querySelectorAll('label')]
    .find(x=>x.textContent.includes('按原操作号、原评审人重试'));
    const input=label?.querySelector('input[type=checkbox]');if(!input)throw new Error('retry confirm missing');input.click()})()`);
  await clickText("按原操作号重试送审");
  await waitFor("document.body?.innerText?.includes('已创建评审')", "submitted review receipt");
  if (submitRequests.length !== 1
    || Object.entries(submitRequests[0].headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1] !== key
    || JSON.stringify(JSON.parse(submitRequests[0].body)) !== JSON.stringify({ reviewer_ids: [reviewer],
      policy_ref: "STRUCTURED_SPEC_ALL_V1", due_at: null, submission_note: null })
    || responses.filter(item => item.url === `${origin}${submitPath}` && item.status === 201).length !== 1
    || await evaluate(`Boolean(sessionStorage.getItem(${JSON.stringify(storageKey)}))`)) {
    throw new Error("Pending submission changed body/Key or did not clear after 201");
  }
  const csrf = Object.entries(submitRequests[0].headers)
    .find(([name]) => name.toLowerCase() === "x-csrf-token")?.[1];
  const originalBody = submitRequests[0].body;
  const replay = await evaluate(`(async()=>{const response=await fetch(${JSON.stringify(submitPath)},
    {method:'POST',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json',
      'Content-Type':'application/json','Idempotency-Key':${JSON.stringify(key)},
      'X-CSRF-Token':${JSON.stringify(csrf)}},body:${JSON.stringify(originalBody)}});
    return {status:response.status,body:await response.json()}})()`);
  if (replay.status !== 201 || replay.body?.data?.state !== "IN_REVIEW"
    || replay.body?.data?.spec_series_id !== series
    || replay.body?.data?.structured_solution_spec_id !== spec
    || submitRequests.length !== 2 || submitRequests[1].body !== originalBody
    || Object.entries(submitRequests[1].headers).find(([name]) => name.toLowerCase() === "idempotency-key")?.[1] !== key) {
    throw new Error(`Exact browser replay failed: ${JSON.stringify(replay)}`);
  }
  const crossStatus = await evaluate(`(async()=>{const response=await fetch(
    ${JSON.stringify(`/api/v1/projects/${otherProject}/structured-solution-specs/${spec}:submit-review`)},
    {method:'POST',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json',
      'Content-Type':'application/json','Idempotency-Key':'structured-spec-review-cross-0001',
      'X-CSRF-Token':${JSON.stringify(csrf)}},body:${JSON.stringify(originalBody)}});return response.status})()`);
  if (crossStatus !== 404) throw new Error(`Cross-project submit returned ${crossStatus}`);
  await route(`/projects/${otherProject}/structured-solution-specs/${spec}`);
  await waitFor("document.body?.innerText?.includes('当前会话没有此项目的读取权限')", "cross-project clear");
  if (await evaluate("document.body.innerText.includes('已创建评审') || document.body.innerText.includes('Solution Review Browser Member')")) {
    throw new Error("Cross-project page retained prior review content");
  }
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  if (typeof screenshot.data !== "string" || screenshot.data.length < 1000) throw new Error("Final page did not render");
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log(`STRUCTURED_SPEC_SUBMIT_EDGE PASS: ${version.product}; manager-only ready validation, active reviewer, exact pending request, 201/replay, cross-project clear, rendered PNG bytes=${Math.floor(screenshot.data.length * 3 / 4)}`);
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill(); await new Promise(resolveExit => edge.once("exit", resolveExit));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Browser profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
