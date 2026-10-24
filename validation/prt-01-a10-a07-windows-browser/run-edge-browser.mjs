/** Real Microsoft Edge proof for the Prototype read/write/session boundary. */
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, projectId, outputRoot] = process.argv.slice(2);
if (!origin?.startsWith("http://127.0.0.1:") || !/^[0-9a-f-]{36}$/.test(projectId ?? "") || !outputRoot) {
  throw new Error("owned arguments required");
}
await mkdir(outputRoot, { recursive: true });
const profile = await mkdtemp(join(tmpdir(), "plm-prt-edge-"));
const port = 10000 + (process.pid % 40000);
const edge = spawn(
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--window-size=1440,2600", `${origin}/login`],
  { stdio: "ignore", windowsHide: true },
);

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function target() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = targets.find(item => item.type === "page" && item.url.startsWith(origin));
      if (page) return page;
    } catch {}
    await pause(100);
  }
  throw new Error("Edge target unavailable");
}

let socket;
let nextId = 0;
const pending = new Map();
const observations = [];
function send(method, params = {}) {
  const id = ++nextId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function waitFor(expression, label, attempts = 400) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      if (await evaluate(`Boolean(${expression})`)) return;
    } catch (error) {
      if (!String(error).includes("Execution context was destroyed")) throw error;
    }
    await pause(100);
  }
  throw new Error(`Timed out ${label}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,16000)})",
  ))}`);
}
async function clickText(text) {
  const clicked = await evaluate(`(()=>{const x=[...document.querySelectorAll('a,button')]
    .find(e=>e.textContent.trim()===${JSON.stringify(text)});if(!x)return false;x.click();return true})()`);
  if (!clicked) throw new Error(`Missing action ${text}`);
}
async function setLabel(label, value, selector = "input,textarea,select") {
  const updated = await evaluate(`(()=>{const l=[...document.querySelectorAll('label')]
    .find(e=>e.textContent.trim().startsWith(${JSON.stringify(label)})),x=l?.querySelector(${JSON.stringify(selector)});
    if(!x)return false;const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(x),'value');
    d.set.call(x,${JSON.stringify(value)});x.dispatchEvent(new Event('input',{bubbles:true}));
    x.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);
  if (!updated) throw new Error(`Missing field ${label}`);
}
async function clickLabelContaining(text) {
  const clicked = await evaluate(`(()=>{const l=[...document.querySelectorAll('label')]
    .find(e=>e.textContent.includes(${JSON.stringify(text)})),x=l?.querySelector('input[type=checkbox]');
    if(!x)return false;if(!x.checked)x.click();return x.checked})()`);
  if (!clicked) throw new Error(`Missing checkbox ${text}: ${JSON.stringify(await evaluate(
    "({url:location.href,text:document.body?.innerText?.slice(0,12000),labels:[...document.querySelectorAll('label')].map(x=>({text:x.textContent.trim(),disabled:x.querySelector('input')?.disabled,checked:x.querySelector('input')?.checked}))})",
  ))}`);
}
async function clickFirstInFieldset(legend) {
  const clicked = await evaluate(`(()=>{const f=[...document.querySelectorAll('fieldset')]
    .find(e=>e.querySelector('legend')?.textContent.includes(${JSON.stringify(legend)}));
    const x=f?.querySelector('input[type=checkbox]');if(!x)return false;if(!x.checked)x.click();return x.checked})()`);
  if (!clicked) throw new Error(`Missing fieldset choice ${legend}: ${JSON.stringify(await evaluate(
    "({text:document.body?.innerText?.slice(0,12000),legends:[...document.querySelectorAll('legend')].map(x=>x.textContent)})",
  ))}`);
}
async function screenshot(name) {
  const result = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  const path = join(outputRoot, name);
  await writeFile(path, Buffer.from(result.data, "base64"));
  return path;
}

try {
  const page = await target();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === "Network.requestWillBeSent" && message.params.request.url.includes("/api/")) {
      observations.push({ request: message.params.request.url, method: message.params.request.method,
        body: message.params.request.postData ?? null });
    }
    if (message.method === "Network.responseReceived" && message.params.response.url.includes("/api/")) {
      observations.push({ url: message.params.response.url, status: message.params.response.status });
    }
    if (message.method === "Runtime.exceptionThrown") observations.push({ exception: message.params.exceptionDetails.text });
    if (!message.id || !pending.has(message.id)) return;
    const operation = pending.get(message.id);
    pending.delete(message.id);
    message.error ? operation.reject(new Error(message.error.message)) : operation.resolve(message.result);
  });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login");
  await evaluate(`(()=>{const set=(s,v)=>{const x=document.querySelector(s),d=Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(x),'value');d.set.call(x,v);x.dispatchEvent(new Event('input',{bubbles:true}))};
    set('#login-username','Synthetic Handover Manager');set('#login-password','synthetic-handover-browser-password')})()`);
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "login success");
  await clickText("我的项目");
  await waitFor("document.body.innerText.includes('Survey schema')", "project list");
  await clickText("Survey schema");
  await waitFor("document.body.innerText.includes('维护项目原型、固定版本与需求覆盖')", "project detail");
  await clickText("维护项目原型、固定版本与需求覆盖");
  await waitFor("document.querySelector('input[maxlength=\"255\"]')&&!document.querySelector('input[maxlength=\"255\"]').disabled&&document.body.innerText.includes('创建原型身份')", "prototype list");

  const prototypeName = "受控审批交互原型";
  await setLabel("原型名称", prototypeName);
  await clickLabelContaining("我确认该名称对应当前项目需要维护的原型范围");
  await clickText("创建原型");
  await waitFor(`document.body.innerText.includes(${JSON.stringify(`原型“${prototypeName}”已创建`)})`, "prototype created");

  await clickText("原型包");
  await waitFor("document.body.innerText.includes('创建原型包')", "package page");
  await setLabel("原型包名称", "实施交付原型包");
  await clickLabelContaining("我确认只创建组织容器");
  await clickText("创建");
  await waitFor("document.body.innerText.includes('原型包已创建')", "package created");
  await clickText("查看并维护成员");
  await waitFor("document.body.innerText.includes('维护：实施交付原型包')", "package detail");
  await clickLabelContaining(prototypeName);
  await clickLabelContaining("我已核对这是期望的完整集合");
  await clickText("完整替换成员");
  await waitFor("document.body.innerText.includes('原型包成员集合已完整替换')", "package members");
  const packageShot = await screenshot("01-package-members.png");

  await clickText("返回原型列表");
  await waitFor("document.body.innerText.includes('原型范围与固定版本')", "prototype list return");
  await clickText("原型模板");
  await waitFor("document.body.innerText.includes('创建项目模板')", "template page");
  await setLabel("模板名称", "审批工作流模板");
  await clickFirstInFieldset("固定项目文档版本");
  await clickLabelContaining("我已人工核对布局、组件、终端和固定文档");
  await clickText("发布首版");
  await waitFor("document.body.innerText.includes('项目模板首版已发布')", "template created");

  await clickText("返回原型列表");
  await waitFor(`document.body.innerText.includes(${JSON.stringify(prototypeName)})`, "prototype list after template");
  await clickText("查看范围、版本和人工维护项");
  await waitFor("document.body.innerText.includes('维护结构化版本')", "prototype detail");
  await clickText("维护结构化版本");
  await waitFor("document.body.innerText.includes('创建不可变DRAFT')", "version page");
  await clickFirstInFieldset("固定文档制品");
  await clickFirstInFieldset("当前已批准需求");
  await setLabel("人工说明", "通过受控表单验证创建、校验和评审提交，不执行任何原型脚本。", "textarea");
  await clickLabelContaining("我已人工核对模板、需求、文档和交互说明");
  await clickText("创建固定DRAFT版本");
  await waitFor("document.body.innerText.includes('不可变DRAFT版本已创建')", "version created");
  await clickText("运行服务端当前事实校验");
  await waitFor("document.body.innerText.includes('服务端当前事实校验通过')", "version validated");
  await clickLabelContaining("Conclusion customer reviewer");
  await clickText("提交正式评审");
  await waitFor("document.body.innerText.includes('评审回执不是批准结论')", "version submitted");
  const reviewShot = await screenshot("02-version-in-review.png");

  await clickText("返回原型详情");
  await waitFor("document.body.innerText.includes('维护需求覆盖关系')", "prototype detail return");
  await clickText("维护需求覆盖关系");
  await waitFor("document.body.innerText.includes('尚无关联记录；这不代表需求无需原型覆盖')", "link history");
  const approvedPrototypeOptions = await evaluate(`(()=>{const l=[...document.querySelectorAll('label')]
    .find(x=>x.textContent.trim().startsWith('当前已批准原型')),s=l?.querySelector('select');
    return s?[...s.options].filter(x=>x.value).length:-1})()`);
  if (approvedPrototypeOptions !== 0) throw new Error("IN_REVIEW version exposed as approved Link candidate");
  const linkShot = await screenshot("03-link-read-boundary.png");

  const protectedUrl = await evaluate("location.href");
  await clickText("账户与登录");
  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='退出登录'&&!x.disabled)", "logout action");
  await clickText("退出登录");
  await waitFor("document.body.innerText.includes('已退出当前会话。')", "logout confirmation");
  await evaluate(`location.assign(${JSON.stringify(protectedUrl)})`);
  await waitFor("document.body.innerText.includes('尚未读取当前身份，请先登录。')", "revoked protected route");
  if (await evaluate("document.body.innerText.includes('受控审批交互原型')")) throw new Error("protected Prototype data remained visible");

  const expected = [
    ["/prototypes", 201],
    ["/prototype-packages", 201],
    [":set-members", 200],
    ["/prototype-templates", 201],
    ["/versions", 201],
    [":validate", 200],
    [":submit-review", 201],
    ["/prototype-requirement-links", 200],
    ["/auth/logout", 200],
  ];
  const missing = expected.filter(([part, status]) => !observations.some(item =>
    typeof item.url === "string" && item.url.includes(part) && item.status === status));
  const exceptions = observations.filter(item => item.exception);
  if (missing.length || exceptions.length) throw new Error(`proof mismatch ${JSON.stringify({ missing, exceptions, observations })}`);
  console.log("PRT_01_A10_A07_WINDOWS_EDGE_BROWSER_PASS");
  console.log(JSON.stringify({ status: "PASS", projectId, screenshots: [packageShot, reviewShot, linkShot],
    observations: observations.length, linkWrite: "NOT_APPLICABLE_UNTIL_APPROVAL" }));
  socket.close();
} catch (error) {
  console.error(JSON.stringify({ observations: observations.map(({ body, ...item }) => item) }, null, 2));
  throw error;
} finally {
  edge.kill();
  await pause(300);
  await rm(profile, { recursive: true, force: true });
}
