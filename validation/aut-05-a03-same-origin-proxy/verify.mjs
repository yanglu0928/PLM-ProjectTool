/** Real Vite network proxy + original Python policy, not authentication acceptance. */
import assert from "node:assert/strict";
import { createServer as httpServer } from "node:http";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath, pathToFileURL } from "node:url";
import { join } from "node:path";
import { createRequire } from "node:module";
import { once } from "node:events";

const root = fileURLToPath(new URL("../../", import.meta.url));
const frontend = join(root, "apps/frontend");
const require = createRequire(join(frontend, "package.json"));
const { createServer, resolveConfig } = await import(pathToFileURL(require.resolve("vite")).href);
const config = await resolveConfig({ root: frontend, configFile: join(frontend, "vite.config.ts") }, "serve");
assert.equal(config.server.cors, false);
for (const key of ["/api/v1", "/health"]) {
  assert.equal(config.server.proxy[key].target, "http://127.0.0.1:8000");
  assert.equal(config.server.proxy[key].changeOrigin, false);
  assert.equal(config.server.proxy[key].rewrite, undefined);
}
const reservation = httpServer();
reservation.listen(0, "127.0.0.1");
await once(reservation, "listening");
const port = reservation.address().port;
await new Promise((done, fail) => reservation.close((error) => error ? fail(error) : done()));
const origin = `http://127.0.0.1:${port}`;
const child = spawn("C:/Users/17231/AppData/Local/Python/pythoncore-3.13-64/python.exe",
  [join(root, "validation/aut-05-a03-same-origin-proxy/probe.py"), origin], {
    windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, PYTHONPATH: join(root, "apps/backend/src"), PYTHONIOENCODING: "utf-8" },
  });
let vite;
try {
  const lines = createInterface({ input: child.stdout });
  const backendPort = await Promise.race([
    once(lines, "line").then(([line]) => Number(line)),
    once(child, "exit").then(() => { throw new Error("Owned probe exited before readiness"); }),
    new Promise((_, reject) => { const timer = setTimeout(() => reject(new Error("Owned probe startup timed out")), 10000); timer.unref(); }),
  ]);
  assert(Number.isInteger(backendPort) && backendPort > 0);
  const target = `http://127.0.0.1:${backendPort}`;
  // Only the target changes to this owned probe, all real proxy options are retained.
  vite = await createServer({ root: frontend, configFile: join(frontend, "vite.config.ts"), logLevel: "silent",
    server: { host: "127.0.0.1", port, strictPort: true, proxy: Object.fromEntries(
      ["/api/v1", "/health"].map((key) => [key, { ...config.server.proxy[key], target }])) } });
  await vite.listen();
  const headers = { Origin: origin, "Content-Type": "application/json", Cookie: "probe_cookie=synthetic",
    "X-CSRF-Token": "synthetic-csrf-probe", "Idempotency-Key": "synthetic-probe-key" };
  const accepted = await fetch(`${origin}/api/v1/auth/login`, { method: "POST", headers, body: '{"probe":true}', signal: AbortSignal.timeout(5000) });
  assert.equal(accepted.status, 418);
  const data = await accepted.json();
  assert.equal(data.policy_allowed, true);
  assert.equal(data.host, `127.0.0.1:${port}`);
  assert.equal(data.origin, origin);
  assert.equal(data.path, "/api/v1/auth/login");
  for (const key of ["body_matches_synthetic", "cookie_matches_synthetic", "csrf_matches_synthetic", "key_matches_synthetic"]) assert.equal(data[key], true);
  assert.equal(accepted.headers.get("access-control-allow-origin"), null);
  const wrong = await fetch(`${origin}/api/v1/auth/login`, { method: "POST", headers: { ...headers, Origin: "http://evil.test" }, body: '{"probe":true}', signal: AbortSignal.timeout(5000) });
  assert.equal(wrong.status, 403);
  const missing = await fetch(`${origin}/api/v1/auth/login`, { method: "POST", signal: AbortSignal.timeout(5000) });
  assert.equal(missing.status, 403);
  const read = await fetch(`${origin}/api/v1/auth/session`, { signal: AbortSignal.timeout(5000) });
  assert.equal(read.status, 418);
  const health = await fetch(`${origin}/health/ready`, { signal: AbortSignal.timeout(5000) });
  assert.equal(health.status, 418);
  assert.equal((await health.json()).path, "/health/ready");
  // Direct backend mismatch proves original gate rejects rewritten backend Host.
  const mismatch = await fetch(`${target}/api/v1/auth/login`, { method: "POST", headers, signal: AbortSignal.timeout(5000) });
  assert.equal(mismatch.status, 403);
  console.log("SAME_ORIGIN_PROXY PASS: actual Vite/Origin policy; 6 cases, preserved Host/Origin/body/Cookie/CSRF/Key; no auth success or production trust");
} finally {
  if (vite) await vite.close();
  if (child.exitCode === null) { child.kill(); await once(child, "exit"); }
}
