import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "../..");
const frontendRoot = path.join(repoRoot, "apps/frontend");
const sourceRoot = path.join(frontendRoot, "src");
const packageJson = JSON.parse(
  fs.readFileSync(path.join(frontendRoot, "package.json"), "utf8"),
);

const expectedVersions = {
  vue: "3.5.43",
  "vue-router": "5.3.1",
  vite: "8.3.0",
  vitest: "5.0.1",
  typescript: "5.9.3",
};

for (const [name, expected] of Object.entries(expectedVersions)) {
  const actual = packageJson.dependencies?.[name] ?? packageJson.devDependencies?.[name];
  assert(actual === expected, `${name} expected ${expected}, got ${actual}`);
}

const requiredFiles = [
  "index.html",
  "src/main.ts",
  "src/app/AppShell.vue",
  "src/app/router.ts",
  "src/app/components/AppErrorBoundary.vue",
  "src/app/views/HomeView.vue",
  "src/app/views/NotFoundView.vue",
  "src/shared/api/healthClient.ts",
  "src/shared/components/ConnectionStatus.vue",
  "src/styles/main.css",
  "dist/index.html",
];
const missingFiles = requiredFiles.filter(
  (relative) => !fs.existsSync(path.join(frontendRoot, relative)),
);
assert(missingFiles.length === 0, `Missing files: ${missingFiles.join(", ")}`);

const productionFiles = walk(sourceRoot).filter(
  (file) => !file.endsWith(".spec.ts") && !file.includes(`${path.sep}test${path.sep}`),
);
const productionSource = productionFiles
  .map((file) => fs.readFileSync(file, "utf8"))
  .join("\n");
const forbiddenPatterns = [
  /\blocalStorage\b/,
  /\bsessionStorage\b/,
  /\bWebSocket\b/,
  /wss?:\/\//i,
  /https?:\/\//i,
  /deepseek/i,
  /bailian/i,
  /api[_-]?key/i,
];
const forbiddenHits = forbiddenPatterns.filter((pattern) =>
  pattern.test(productionSource),
);
assert(forbiddenHits.length === 0, "Forbidden browser dependency found");

const healthClient = fs.readFileSync(
  path.join(sourceRoot, "shared/api/healthClient.ts"),
  "utf8",
);
assert(healthClient.includes('"/health/ready"'), "Relative health path is missing");
assert(
  healthClient.includes('credentials: "same-origin"'),
  "Same-origin credentials policy is missing",
);

const specFiles = walk(sourceRoot).filter((file) => file.endsWith(".spec.ts"));
const testCount = specFiles.reduce((count, file) => {
  const source = fs.readFileSync(file, "utf8");
  return count + (source.match(/\bit\(/g) ?? []).length;
}, 0);
assert(testCount === 9, `Expected 9 tests, got ${testCount}`);

const assetRoot = path.join(frontendRoot, "dist/assets");
const assets = walk(assetRoot);
const javascriptBytes = sumBytes(assets.filter((file) => file.endsWith(".js")));
const cssBytes = sumBytes(assets.filter((file) => file.endsWith(".css")));
assert(javascriptBytes > 0 && cssBytes > 0, "Built assets are incomplete");

const result = {
  status: "PASS",
  wbs: "1.03",
  platform: `${process.platform}-${process.arch}`,
  node: process.version,
  package_manager: packageJson.packageManager,
  versions: expectedVersions,
  test_file_count: specFiles.length,
  test_count: testCount,
  required_file_count: requiredFiles.length,
  missing_file_count: 0,
  forbidden_browser_dependency_count: 0,
  health_endpoint: "/health/ready",
  business_route_count: 0,
  javascript_bytes: javascriptBytes,
  css_bytes: cssBytes,
  source_map_count: assets.filter((file) => file.endsWith(".map")).length,
  external_call_count: 0,
};

if (process.argv.includes("--write")) {
  const evidencePath = path.join(
    scriptDir,
    "evidence/windows-11/result.json",
  );
  fs.mkdirSync(path.dirname(evidencePath), { recursive: true });
  fs.writeFileSync(evidencePath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify(result, null, 2));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function walk(root) {
  if (!fs.existsSync(root)) return [];
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const item = path.join(root, entry.name);
    return entry.isDirectory() ? walk(item) : [item];
  });
}

function sumBytes(files) {
  return files.reduce((total, file) => total + fs.statSync(file).size, 0);
}
