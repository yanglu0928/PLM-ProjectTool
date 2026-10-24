/** Owned headless Edge network proof for SectionVersion CREATE. */
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";

const [origin, project, otherProject, section, documentVersion,
  requirement, requirementVersion, evidence, token, csrf] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(origin ?? "")
  || ![project, otherProject, section, documentVersion, requirement,
    requirementVersion, evidence].every(value => uuid.test(value ?? ""))
  || !/^[0-9a-f]{64}$/.test(token ?? "") || !/^[0-9a-f]{64}$/.test(csrf ?? "")) {
  throw new Error("owned synthetic inputs required");
}
const profile = await mkdtemp(join(tmpdir(), "plm-section-version-edge-"));
const cdpPort = 10000 + process.pid % 40000;
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ["--headless=new", `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-features=msEdgeFirstRunExperience",
    "about:blank"], { stdio: "ignore", windowsHide: true });
const pause = ms => new Promise(done => setTimeout(done, ms));
let socket; let serial = 0;
const pending = new Map();
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
function send(method, params = {}) {
  const id = ++serial;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, rejectCall) => pending.set(id, {
    resolve: resolveCall, reject: rejectCall,
  }));
}
async function evaluate(expression) {
  const response = await send("Runtime.evaluate", {
    expression, awaitPromise: true, returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(`Browser exception: ${response.exceptionDetails.text}`);
  }
  return response.result.value;
}
async function request(path, body, key, csrfValue = csrf) {
  return await evaluate(`(async()=>{
    const headers={'content-type':'application/json','x-csrf-token':${JSON.stringify(csrfValue)}};
    if(${JSON.stringify(key)}!==null) headers['idempotency-key']=${JSON.stringify(key)};
    const response=await fetch(${JSON.stringify(path)}, {
      method:'POST',credentials:'same-origin',headers,
      body:JSON.stringify(${JSON.stringify(body)}),
    });
    return {status:response.status, location:response.headers.get('location'),
      body:await response.json()};
  })()`);
}
const path = `/api/v1/projects/${project}/solution-sections/${section}/versions`;
const payload = {
  title: "Edge network section body",
  content_document_version_ref: documentVersion,
  content_artifact_ref: null,
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  evidence_ids: [evidence], assumptions: [{ note: "synthetic edge" }], exclusions: [],
};
try {
  const page = await findPage();
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((opened, failed) => {
    socket.addEventListener("open", opened, { once: true });
    socket.addEventListener("error", failed, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (!message.id || !pending.has(message.id)) return;
    const task = pending.get(message.id); pending.delete(message.id);
    message.error ? task.reject(new Error(message.error.message)) : task.resolve(message.result);
  });
  await send("Page.enable"); await send("Network.enable"); await send("Runtime.enable");
  await send("Network.setCookie", {
    name: "plm_session", value: token, url: origin, httpOnly: true, sameSite: "Strict",
  });
  await send("Page.navigate", { url: `${origin}/openapi.json` });
  for (let n = 0; n < 100; n += 1) {
    if (await evaluate(`location.origin===${JSON.stringify(origin)}`)) break;
    await pause(50);
  }
  if (!await evaluate(`location.origin===${JSON.stringify(origin)}`)) {
    throw new Error("Edge did not enter owned origin");
  }
  const first = await request(path, payload, "section-edge-create-0001");
  if (first.status !== 201 || first.body.data.version_no !== 6
    || first.body.data.version_state !== "DRAFT"
    || first.location !== `${path}/${first.body.data.solution_section_version_id}`) {
    throw new Error(`Edge create failed: ${JSON.stringify(first)}`);
  }
  const replay = await request(path, payload, "section-edge-create-0001");
  if (replay.status !== 201 || JSON.stringify(replay.body.data) !== JSON.stringify(first.body.data)) {
    throw new Error("Edge replay mismatch");
  }
  const conflict = await request(path, { ...payload, title: "different" }, "section-edge-create-0001");
  if (conflict.status !== 409) throw new Error(`Edge idempotency conflict ${conflict.status}`);
  const cross = await request(path.replace(project, otherProject), payload, "section-edge-cross-0001");
  if (cross.status !== 404) throw new Error(`Edge cross-project leak ${cross.status}`);
  const badCsrf = await request(path, payload, "section-edge-csrf-0001", "00".repeat(32));
  if (badCsrf.status !== 403) throw new Error(`Edge CSRF rejection ${badCsrf.status}`);
  const noKey = await request(path, payload, null);
  if (noKey.status !== 422) throw new Error(`Edge missing-key rejection ${noKey.status}`);
  const artifact = await request(path, {
    ...payload, content_document_version_ref: null,
    content_artifact_ref: "00000000-0000-4000-8000-000000000001",
  }, "section-edge-artifact-0001");
  if (artifact.status !== 503) throw new Error(`Edge unavailable artifact ${artifact.status}`);
  console.log("SECTION_VERSION_EDGE_NETWORK PASS: 201/replay/409/404/403/422/503");
} finally {
  try { socket?.close(); } catch { /* already closed */ }
  edge.kill();
  await new Promise(done => edge.once("exit", done));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep)) {
    throw new Error("Browser profile escaped temp root");
  }
  await rm(profile, { recursive: true, force: true });
}
