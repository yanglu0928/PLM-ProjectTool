/** Edge CDP fallback for environments where the managed browser kernel is unavailable. */
import { spawn } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [origin, projectId, outputRoot, mode] = process.argv.slice(2);
const verifyWorkbench = mode === "--workbench";
if (!origin?.startsWith("http://127.0.0.1:") || !/^[0-9a-f-]{36}$/.test(projectId ?? "") || !outputRoot) {
  throw new Error("origin, project id and output root required");
}
const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profile = await mkdtemp(join(tmpdir(), "plm-ai05-edge-"));
const debuggingPort = 10000 + (process.pid % 40000);
const browser = spawn(edge, [
  "--headless=new", `--remote-debugging-port=${debuggingPort}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
  "--window-size=1440,1200", `${origin}/login`,
], { stdio: "ignore", windowsHide: true });

const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
async function target() {
  for (let count = 0; count < 100; count += 1) {
    try {
      const entries = await (await fetch(`http://127.0.0.1:${debuggingPort}/json/list`)).json();
      const page = entries.find((entry) => entry.type === "page" && entry.url.startsWith(origin));
      if (page) return page;
    } catch { /* Edge is starting. */ }
    await pause(100);
  }
  throw new Error("Edge DevTools target unavailable");
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
  const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
  return response.result.value;
}
async function waitFor(expression, label) {
  for (let count = 0; count < 200; count += 1) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await pause(100);
  }
  const diagnostic = await evaluate("({ url: location.href, title: document.title, text: document.body?.innerText?.slice(0, 4000) ?? '' })");
  throw new Error(`Timed out waiting for ${label}: ${JSON.stringify({ diagnostic, observations: observations.slice(-30) })}`);
}
async function clickText(text) {
  const clicked = await evaluate(`(() => { const node = [...document.querySelectorAll('a,button')]
    .find((item) => item.textContent.trim() === ${JSON.stringify(text)}); if (!node) return false; node.click(); return true; })()`);
  if (!clicked) throw new Error(`Missing action: ${text}`);
}
async function clickTextStartingWith(text) {
  const clicked = await evaluate(`(() => { const node = [...document.querySelectorAll('a,button')]
    .find((item) => item.textContent.trim().startsWith(${JSON.stringify(text)})); if (!node) return false; node.click(); return true; })()`);
  if (!clicked) throw new Error(`Missing action starting with: ${text}`);
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
    if (message.method === "Network.responseReceived") {
      const response = message.params.response;
      if (response.url.includes("/api/")) observations.push({ type: "response", url: response.url, status: response.status,
        mimeType: response.mimeType });
    } else if (message.method === "Network.loadingFailed") {
      observations.push({ type: "failed", errorText: message.params.errorText, canceled: message.params.canceled });
    } else if (message.method === "Runtime.exceptionThrown") {
      observations.push({ type: "exception", text: message.params.exceptionDetails.text });
    }
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Network.enable");
  await waitFor("document.querySelector('#login-username')", "login form");
  await evaluate(`(() => { const set = (selector, value) => { const input = document.querySelector(selector);
    input.value = value; input.dispatchEvent(new Event('input', { bubbles: true })); };
    set('#login-username', 'Synthetic AI Manager'); set('#login-password', 'synthetic-ai-browser-password');
    return true; })()`);
  await waitFor("!document.querySelector('button[type=submit]').disabled", "enabled login action");
  await evaluate("document.querySelector('button[type=submit]').click()");
  await waitFor("document.body.innerText.includes('登录成功。')", "successful login");
  await clickText("我的项目");
  await waitFor("document.body.innerText.includes('Synthetic AI Browser Project')", "project list");
  await clickText("Synthetic AI Browser Project");
  await waitFor("document.body.innerText.includes('查看AI任务与建议状态')", "project detail");
  await clickText("查看AI任务与建议状态");
  await waitFor("document.body.innerText.includes('新建AI分析任务')", "AI workbench");
  await clickText("新建AI分析任务");
  await waitFor("document.body.innerText.includes('Synthetic Local Route')", "safe options and document list");
  const chosen = await evaluate(`(() => { const input = document.querySelector('.document-choice input[type=checkbox]');
    if (!input) return false; input.click(); return input.checked; })()`);
  if (!chosen) throw new Error("Synthetic document could not be selected");
  await screenshot("01-options.png");
  await clickText("生成外发预览（不会发送）");
  await waitFor("document.querySelector('section.preview')", "egress preview");
  await screenshot("02-preview.png");
  const approved = await evaluate(`(() => { const input = document.querySelector('.approval input[type=checkbox]');
    if (!input) return false; input.click(); return input.checked; })()`);
  if (!approved) throw new Error("Explicit approval checkbox could not be selected");
  await clickText("明确授权本轮外发");
  await waitFor("document.querySelector('section.authorization')", "egress authorization");
  await screenshot("03-authorization.png");
  await clickText("创建AI任务");
  await waitFor("document.querySelector('section.created')", "created AI task");
  const result = await evaluate(`(() => ({ text: document.querySelector('section.created').innerText,
    alerts: [...document.querySelectorAll('[role=alert]')].map((item) => item.innerText),
    url: location.href }))()`);
  if (result.alerts.length || !result.text.includes("任务已创建") || result.url !== `${origin}/projects/${projectId}/ai/new`) {
    throw new Error(`Unexpected browser result: ${JSON.stringify(result)}`);
  }
  const finalShot = await screenshot("04-created.png");
  if (!verifyWorkbench) {
    console.log(JSON.stringify({ status: "PASS", ...result, screenshot: finalShot }));
  } else {
    const identifiers = await evaluate(`(() => {
      const links = [...document.querySelectorAll('section.created a')];
      const task = links.find((item) => item.textContent.trim() === '查看AI任务详情');
      const href = task?.getAttribute('href') ?? '';
      const taskId = href.split('/').at(-1) ?? null;
      return { taskId: /^[0-9a-f-]{36}$/.test(taskId ?? '') ? taskId : null };
    })()`);
    if (!identifiers.taskId) throw new Error("Created task identifier was not exposed by the safe detail link");
    await clickText("查看AI任务详情");
    await waitFor("document.body.innerText.includes('当前任务尚无可见调用记录。')", "AI task detail and empty invocation history");
    const taskDetail = await evaluate(`(() => ({ text: document.querySelector('.ai-task-detail')?.innerText ?? '',
      jobHref: [...document.querySelectorAll('.ai-task-detail a')].find((item) => item.textContent.trim().startsWith('打开运行任务'))?.getAttribute('href') ?? null,
      alerts: [...document.querySelectorAll('[role=alert]')].map((item) => item.innerText), url: location.href }))()`);
    if (taskDetail.alerts.length || !taskDetail.text.includes('QUEUED') || !taskDetail.text.includes('NONE（仍需人工确认）')
        || !taskDetail.text.includes('固定版本') || !taskDetail.jobHref?.match(/\/jobs\/[0-9a-f-]{36}$/)) {
      throw new Error(`Unexpected task detail: ${JSON.stringify(taskDetail)}`);
    }
    const jobId = taskDetail.jobHref.split('/').at(-1);
    await screenshot("05-task-detail.png");
    await clickTextStartingWith("打开运行任务");
    await waitFor("document.body.innerText.includes('运行任务详情') && document.body.innerText.includes('AI_TASK_EXECUTE')", "job detail");
    const jobDetail = await evaluate(`(() => ({ text: document.body.innerText,
      alerts: [...document.querySelectorAll('[role=alert]')].map((item) => item.innerText), url: location.href }))()`);
    if (jobDetail.alerts.length || !jobDetail.text.includes('状态\nPENDING') || !jobDetail.text.includes('来源模块\nai')
        || jobDetail.url !== `${origin}/projects/${projectId}/jobs/${jobId}`) {
      throw new Error(`Unexpected job detail: ${JSON.stringify(jobDetail)}`);
    }
    await screenshot("06-job-detail.png");
    await evaluate("history.back(); true");
    await waitFor("document.body.innerText.includes('任务详情与运行历史') && document.body.innerText.includes('当前任务尚无可见调用记录。')", "task detail after browser back");
    await clickText("返回AI任务列表");
    await waitFor(`document.body.innerText.includes('任务与建议状态') && document.body.innerText.includes(${JSON.stringify(identifiers.taskId)})`, "created task in workbench list");
    const workbench = await evaluate(`(() => ({ text: document.querySelector('.ai-workbench')?.innerText ?? '',
      alerts: [...document.querySelectorAll('[role=alert]')].map((item) => item.innerText), url: location.href }))()`);
    if (workbench.alerts.length || !workbench.text.includes('等待执行') || !workbench.text.includes('暂无建议')
        || !workbench.text.includes(jobId) || workbench.url !== `${origin}/projects/${projectId}/ai`) {
      throw new Error(`Unexpected workbench list: ${JSON.stringify(workbench)}`);
    }
    const workbenchShot = await screenshot("07-workbench.png");
    const apiResponses = observations.filter((item) => item.type === 'response');
    const requiredFragments = [
      `/ai-tasks/${identifiers.taskId}`,
      `/ai-tasks/${identifiers.taskId}/invocations`,
      `/jobs/${jobId}`,
      `/projects/${projectId}/ai-tasks?page_size=50`,
    ];
    const missing = requiredFragments.filter((fragment) => !apiResponses.some((item) => item.status === 200 && item.url.includes(fragment)));
    if (missing.length) throw new Error(`Missing successful API observations: ${JSON.stringify({ missing, apiResponses })}`);
    console.log("AI_05_A07_WINDOWS_WORKBENCH_PASS");
    console.log(JSON.stringify({ status: "PASS", taskId: identifiers.taskId, jobId,
      taskState: "QUEUED", suggestionState: "NONE", jobState: "PENDING", invocationCount: 0,
      screenshots: [finalShot, join(outputRoot, "05-task-detail.png"), join(outputRoot, "06-job-detail.png"), workbenchShot],
      observedApiResponses: requiredFragments.length }));
  }
  socket.close();
} finally {
  browser.kill();
  await pause(300);
  await rm(profile, { recursive: true, force: true });
}
