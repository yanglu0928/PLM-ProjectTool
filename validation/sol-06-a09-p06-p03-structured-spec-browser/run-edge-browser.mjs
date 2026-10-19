/** Owned headless Edge proof of actual SOL-06 DRAFT creation and exact replay. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, section, _document, _documentVersion,
  requirement, requirementVersion, evidence] = process.argv.slice(2);
const password = process.env.PLM_BROWSER_SYNTHETIC_PASSWORD;
const detailMode = process.env.PLM_SPEC_DETAIL_ACCEPTANCE === "1";
const listMode = process.env.PLM_SPEC_LIST_ACCEPTANCE === "1";
const reviseMode = process.env.PLM_SPEC_REVISE_ACCEPTANCE === "1";
const validateMode = process.env.PLM_SPEC_VALIDATE_ACCEPTANCE === "1";
const staleSpecId = process.env.PLM_STALE_SPEC_ID;
const currentRequirementVersion = process.env.PLM_CURRENT_REQUIREMENT_VERSION;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, section, requirement, requirementVersion,
    evidence].every(value => uuid.test(value ?? ""))
  || project === otherProject || typeof password !== "string" || password.length < 24) {
  throw new Error("owned synthetic inputs required");
}
if (listMode && !detailMode) throw new Error("List acceptance requires detail acceptance");
if (reviseMode && (!detailMode || !uuid.test(staleSpecId ?? "")
  || !uuid.test(currentRequirementVersion ?? ""))) {
  throw new Error("Revise acceptance requires detail, stale spec and current requirement version");
}
if (validateMode && !detailMode) {
  throw new Error("Structured spec validation acceptance requires detail acceptance");
}
const activeRequirementVersion = reviseMode ? currentRequirementVersion : requirementVersion;
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
const pending = new Map(); const responses = []; const requests = []; const reviseRequests = [];
const validateRequests = [];
const errors = [];
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
let createdSpecId = null;
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
    if (event.method === "Network.requestWillBeSent"
      && event.params.request.url.startsWith(
        `${origin}/api/v1/projects/${project}/structured-solution-specs/`)
      && event.params.request.url.endsWith(":revise")) {
      reviseRequests.push({ url: event.params.request.url,
        headers: event.params.request.headers, body: event.params.request.postData });
    }
    if (event.method === "Network.requestWillBeSent"
      && event.params.request.url.startsWith(
        `${origin}/api/v1/projects/${project}/structured-solution-specs/`)
      && event.params.request.url.endsWith(":validate")) {
      validateRequests.push({ url: event.params.request.url,
        headers: event.params.request.headers, body: event.params.request.postData });
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
    || body.requirement_refs?.[0]?.requirement_version_id !== activeRequirementVersion
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
    createdSpecId = specId;
    const detailPath = `/api/v1/projects/${project}/structured-solution-specs/${specId}`;
    await waitFor(`document.body?.innerText?.includes(${JSON.stringify(activeRequirementVersion)}) &&
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
    if (validateMode) {
      await clickText("验证当前事实");
      await waitFor("document.body?.innerText?.includes('固定内容与主要来源核验通过')",
        "structured spec validation report");
      const validatePath = `/api/v1/projects/${project}/structured-solution-specs/${specId}:validate`;
      if (validateRequests.length !== 1 || validateRequests[0].url !== `${origin}${validatePath}`
        || validateRequests[0].body !== undefined
        || responses.filter(item => item.url === `${origin}${validatePath}`
          && item.status === 200).length !== 1) {
        throw new Error(`First real VALIDATE 200 missing: ${JSON.stringify(validateRequests)}`);
      }
      const originalValidate = validateRequests[0];
      const validateKey = Object.entries(originalValidate.headers)
        .find(([name]) => name.toLowerCase() === "idempotency-key")?.[1];
      const validateCsrf = Object.entries(originalValidate.headers)
        .find(([name]) => name.toLowerCase() === "x-csrf-token")?.[1];
      const validationView = await evaluate(`(()=>({text:document.body.innerText,
        audit:[...document.querySelectorAll('.validation-report code')][0]?.textContent}))()`);
      if (typeof validateKey !== "string" || typeof validateCsrf !== "string"
        || !uuid.test(validationView.audit ?? "")
        || !["尚不具备送审条件；不得视为已批准。", "固定版本完整性：通过",
          "类型化内容结构：通过", "需求来源：通过", "章节来源：通过",
          "证据来源：通过", "输出附件：通过", "追溯覆盖：暂无法核验",
          "当前缺少专项到需求/章节的可信追溯覆盖。", "系列当前版本：通过",
          "SCOPE_MAPPING：通过"].every(part => validationView.text.includes(part))) {
        throw new Error(`Validation report or maintenance guidance invalid: ${JSON.stringify(validationView)}`);
      }
      const validationStorageKey = `plm.sol.structured-spec.validate.pending.${actor}.${project}.${specId}`;
      const validationPending = JSON.stringify({ actor, project, spec: specId, key: validateKey });
      await evaluate(`sessionStorage.setItem(${JSON.stringify(validationStorageKey)},
        ${JSON.stringify(validationPending)})`);
      await route(`/projects/${project}/solution-sections`);
      await waitFor("document.body?.innerText?.includes('方案章节')", "leave validated detail");
      await route(`/projects/${project}/structured-solution-specs/${specId}`);
      await waitFor("document.body?.innerText?.includes('存在结果未知的原验证操作')",
        "validation pending restored");
      if (await evaluate("document.querySelector('.validation-report')!==null")) {
        throw new Error("Old validation report survived detail reload");
      }
      await evaluate("[...document.querySelectorAll('input[type=checkbox]')].at(-1)?.click()");
      await clickText("按原操作号重试验证");
      await waitFor("document.body?.innerText?.includes('固定内容与主要来源核验通过')",
        "validation receipt replayed");
      if (validateRequests.length !== 2
        || Object.entries(validateRequests[1].headers)
          .find(([name]) => name.toLowerCase() === "idempotency-key")?.[1] !== validateKey
        || validateRequests[1].body !== undefined
        || responses.filter(item => item.url === `${origin}${validatePath}`
          && item.status === 200).length !== 2
        || await evaluate(`Boolean(sessionStorage.getItem(${JSON.stringify(validationStorageKey)}))`)) {
        throw new Error("Original validation key was not replayed exactly or pending survived");
      }
      const crossValidateStatus = await evaluate(`(async()=>{const response=await fetch(
        ${JSON.stringify(`/api/v1/projects/${otherProject}/structured-solution-specs/${specId}:validate`)},
        {method:'POST',credentials:'same-origin',headers:{'Accept':'application/json',
          'Idempotency-Key':'structured-spec-cross-validate-0001',
          'X-CSRF-Token':${JSON.stringify(validateCsrf)}}});return response.status})()`);
      if (crossValidateStatus !== 404) {
        throw new Error(`Cross-project validation returned ${crossValidateStatus}`);
      }
    }
    if (reviseMode) {
      await clickText("基于此版本创建修订草案");
      await waitFor("document.querySelector('#spec-revise-title') && document.querySelector('#revise-source')",
        "revision form");
      const prefill = await evaluate(`(()=>({source:document.querySelector('#revise-source')?.value,
        scope:document.querySelector('#revise-scope')?.value,
        requirement:document.querySelector(${JSON.stringify(`input[value="${requirement}"]`)})?.checked,
        section:document.querySelector(${JSON.stringify(`input[value="${section}"]`)})?.checked,
        evidence:document.querySelector(${JSON.stringify(`input[value="${evidence}"]`)})?.checked}))()`);
      if (prefill.source !== "Old PLM" || prefill.scope !== "Parts"
        || !prefill.requirement || !prefill.section || !prefill.evidence) {
        throw new Error(`Fixed revision prefill mismatch: ${JSON.stringify(prefill)}`);
      }
      await setValue("#revise-scope", "Parts and BOM");
      await evaluate("[...document.querySelectorAll('form input[type=checkbox]')].at(-1)?.click()");
      await clickText("创建修订 DRAFT");
      await waitFor("document.body?.innerText?.includes('修订草案。当前仅为 DRAFT')",
        "created revision DRAFT");
      const revisePath = `/api/v1/projects/${project}/structured-solution-specs/${specId}:revise`;
      if (reviseRequests.length !== 1 || reviseRequests[0].url !== `${origin}${revisePath}`
        || responses.filter(item => item.url === `${origin}${revisePath}`
          && item.status === 201).length !== 1) {
        throw new Error("First real REVISE 201 missing");
      }
      const originalRevise = reviseRequests[0];
      const reviseKey = Object.entries(originalRevise.headers)
        .find(([name]) => name.toLowerCase() === "idempotency-key")?.[1];
      const csrf = Object.entries(originalRevise.headers)
        .find(([name]) => name.toLowerCase() === "x-csrf-token")?.[1];
      const reviseBody = JSON.parse(originalRevise.body);
      if (typeof reviseKey !== "string" || typeof csrf !== "string"
        || reviseBody.payload?.scope !== "Parts and BOM"
        || reviseBody.requirement_refs?.[0]?.requirement_version_id !== activeRequirementVersion
        || reviseBody.section_refs?.[0]?.solution_section_id !== section
        || reviseBody.evidence_ids?.[0] !== evidence || reviseBody.artifact_ids?.length !== 0) {
        throw new Error("Browser revision request mismatch");
      }
      const revisedSpecId = await evaluate(`(()=>{const link=[...document.querySelectorAll('a')]
        .find(node=>node.textContent.trim()==='查看新版本');return link?.pathname.split('/').at(-1)})()`);
      if (!uuid.test(revisedSpecId)) throw new Error("Revised detail link has no version identity");
      await evaluate(`(()=>sessionStorage.setItem(${JSON.stringify(
        `plm.sol.spec.revise.pending.${actor}.${project}.${specId}`)},JSON.stringify(${JSON.stringify({
        project, predecessor: specId, actor, draft: reviseBody, key: reviseKey,
      })})))()`);
      await route(`/projects/${project}/structured-solution-specs/${specId}`);
      await waitFor("document.querySelector('#spec-detail-title')", "leave revision page");
      await route(`/projects/${project}/structured-solution-specs/${specId}/revise`);
      await waitFor("document.body?.innerText?.includes('存在原修订操作')", "revision pending restore");
      if (await evaluate("document.querySelector('#revise-source')!==null")) {
        throw new Error("Pending revision allowed changed body");
      }
      await evaluate("document.querySelector('form input[type=checkbox]').click()");
      await clickText("按原操作号重试");
      await waitFor("document.body?.innerText?.includes('修订草案。当前仅为 DRAFT')",
        "replayed revision receipt");
      if (reviseRequests.length !== 2 || reviseRequests[1].body !== originalRevise.body
        || Object.entries(reviseRequests[1].headers)
          .find(([name]) => name.toLowerCase() === "idempotency-key")?.[1] !== reviseKey
        || responses.filter(item => item.url === `${origin}${revisePath}`
          && item.status === 201).length !== 2) {
        throw new Error("Original revision key replay changed request or did not return 201");
      }
      await clickText("查看新版本");
      await waitFor("document.querySelector('#spec-detail-title') && document.body.innerText.includes('Parts and BOM')",
        "revised fixed detail");
      const revisedReceipt = await evaluate(`(async()=>{const response=await fetch(
        ${JSON.stringify(`/api/v1/projects/${project}/structured-solution-specs/${revisedSpecId}`)},
        {credentials:'same-origin',cache:'no-store'});return {status:response.status,body:await response.json()}})()`);
      if (revisedReceipt.status !== 200 || revisedReceipt.body?.data?.version_no !== 2
        || revisedReceipt.body?.data?.version_state !== "DRAFT"
        || revisedReceipt.body?.data?.supersedes_version_ref !== specId
        || revisedReceipt.body?.data?.payload?.scope !== "Parts and BOM") {
        throw new Error(`Revised fixed detail mismatch: ${JSON.stringify(revisedReceipt)}`);
      }
      const crossReviseStatus = await evaluate(`(async()=>{const response=await fetch(
        ${JSON.stringify(`/api/v1/projects/${otherProject}/structured-solution-specs/${specId}:revise`)},
        {method:'POST',credentials:'same-origin',headers:{'Accept':'application/json',
          'Content-Type':'application/json','Idempotency-Key':${JSON.stringify(reviseKey)},
          'X-CSRF-Token':${JSON.stringify(csrf)}},body:${JSON.stringify(originalRevise.body)}});
        return response.status})()`);
      if (crossReviseStatus !== 404) throw new Error(`Cross-project revise returned ${crossReviseStatus}`);
      await route(`/projects/${project}/structured-solution-specs/${staleSpecId}/revise`);
      await waitFor("document.body?.innerText?.includes('系统没有自动替换')",
        "historical source drift warning");
      if (await evaluate(`document.querySelector(${JSON.stringify(
        `input[value="${requirement}"]`)})?.checked!==false`)) {
        throw new Error("Stale requirement source was silently replaced");
      }
      await route(`/projects/${otherProject}/structured-solution-specs/${specId}/revise`);
      await waitFor("document.body?.innerText?.includes('仅当前项目负责人或实施成员可修订')",
        "cross-project revision page denied");
      if (await evaluate("document.querySelector('form')!==null || document.body.innerText.includes('Parts and BOM')")) {
        throw new Error("Cross-project revision page leaked editable or prior content");
      }
    }
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
    if (validateMode && await evaluate("document.querySelector('.validation-report')!==null")) {
      throw new Error("Cross-project detail retained prior validation report");
    }
    if (responses.some(item => item.url === `${origin}${crossPath}` && item.status === 200)) {
      throw new Error("Cross-project detail leaked HTTP 200");
    }
  }
  if (listMode) {
    await route(`/projects/${project}`);
    await waitFor("document.body?.innerText?.includes('查看结构化专项版本')",
      "project detail structured spec entry");
    if (!responses.some(item => item.url === `${origin}/api/v1/projects/${project}`
      && item.status === 200)) throw new Error("Real project detail GET 200 missing");
    await clickText("查看结构化专项版本");
    await waitFor("document.querySelector('#spec-list-title') && document.querySelectorAll('.spec-list ol>li').length===50",
      "first structured spec history page");
    const firstPage = await evaluate(`(()=>({text:document.body.innerText,
      count:document.querySelectorAll('.spec-list ol>li').length,
      detailLinks:[...document.querySelectorAll('.spec-list ol a')].map(x=>x.getAttribute('href')),
      load:[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='加载更早版本')}))()`);
    if (firstPage.count !== 50 || !firstPage.load
      || !firstPage.text.includes("不可变版本摘要")
      || !firstPage.text.includes("待评审草案")
      || firstPage.text.includes("field_mappings")) {
      throw new Error(`First list projection invalid: ${JSON.stringify(firstPage)}`);
    }
    const listPrefix = `${origin}/api/v1/projects/${project}/structured-solution-specs?`;
    if (!responses.some(item => item.url.startsWith(listPrefix)
      && item.url.includes("page_size=50") && item.status === 200)) {
      throw new Error("Real first list GET 200 missing");
    }
    await clickText("加载更早版本");
    await waitFor("document.querySelectorAll('.spec-list ol>li').length===51",
      "second structured spec history page");
    if (await evaluate("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='加载更早版本')")) {
      throw new Error("Final list page retained next action");
    }
    if (responses.filter(item => item.url.startsWith(listPrefix) && item.status === 200).length < 2
      || !responses.some(item => item.url.startsWith(listPrefix) && item.url.includes("cursor="))) {
      throw new Error("Real signed second list GET 200 missing");
    }
    if (!createdSpecId || !await evaluate(`Boolean(document.querySelector(
      ${JSON.stringify(`a[href="/projects/${project}/structured-solution-specs/${createdSpecId}"]`)}))`)) {
      throw new Error("Created fixed detail absent from complete history");
    }
    await evaluate(`document.querySelector(${JSON.stringify(
      `a[href="/projects/${project}/structured-solution-specs/${createdSpecId}"]`)}).click()`);
    await waitFor("document.querySelector('#spec-detail-title') && document.body.innerText.includes('Old PLM')",
      "history to fixed detail navigation");
    const crossListPath = `/api/v1/projects/${otherProject}/structured-solution-specs?page_size=50`;
    const directCrossListStatus = await evaluate(`(async()=>{
      const response=await fetch(${JSON.stringify(crossListPath)},
        {credentials:'same-origin',cache:'no-store'});return response.status})()`);
    if (directCrossListStatus !== 404) {
      throw new Error(`Cross-project list returned ${directCrossListStatus}`);
    }
    await route(`/projects/${otherProject}/structured-solution-specs`);
    await waitFor("document.body?.innerText?.includes('当前会话没有此项目的读取权限')",
      "cross-project list denied");
    if (await evaluate("document.querySelectorAll('.spec-list ol>li').length!==0 || document.body.innerText.includes('Old PLM')")) {
      throw new Error("Cross-project list retained prior history");
    }
  }
  await route(`/projects/${otherProject}/structured-solution-specs/new`);
  await waitFor("document.body?.innerText?.includes('创建结构化专项草案')", "cross-project route");
  if (await evaluate("document.querySelector('form')!==null")) throw new Error("Cross-project create leaked");
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`);
  console.log(validateMode
    ? "STRUCTURED_SPEC_VALIDATE_EDGE PASS: first observation, original-key replay, maintenance guidance, cross-project clear"
    : reviseMode
    ? "STRUCTURED_SPEC_REVISE_EDGE PASS: fixed prefill, real v2 DRAFT, original-key replay, source drift, cross-project hidden"
    : listMode
    ? "STRUCTURED_SPEC_LIST_EDGE PASS: project entry, signed two-page history, fixed detail, cross-project 404/clear"
    : detailMode
    ? "STRUCTURED_SPEC_DETAIL_EDGE PASS: create/replay, real detail GET, fixed links, cross-project 404/hidden"
    : "STRUCTURED_SPEC_CREATE_EDGE PASS: current candidates, real DRAFT 201, original-key replay, cross-project hidden");
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill();
  await new Promise(resolveExit => edge.once("exit", resolveExit));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) throw new Error("Browser profile escaped temp root");
  await rm(profile, { recursive: true, force: true });
}
