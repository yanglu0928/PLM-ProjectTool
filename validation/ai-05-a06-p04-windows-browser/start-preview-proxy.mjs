/** Owned validation proxy: built frontend assets plus same-origin API forwarding. */
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { join } from "node:path";
import { createInterface } from "node:readline";

const root = fileURLToPath(new URL("../../", import.meta.url));
const frontend = join(root, "apps/frontend");
const require = createRequire(join(frontend, "package.json"));
const { preview } = await import(pathToFileURL(require.resolve("vite")).href);
const [port, backend] = process.argv.slice(2).map(Number);
if (![port, backend].every((value) => Number.isInteger(value) && value > 0 && value <= 65535)) {
  throw new Error("Invalid owned validation port");
}
const target = `http://127.0.0.1:${backend}`;
const server = await preview({
  root: frontend,
  configFile: join(frontend, "vite.config.ts"),
  logLevel: "silent",
  preview: {
    host: "127.0.0.1",
    port,
    strictPort: true,
    proxy: Object.fromEntries(["/api/v1", "/health"].map((key) => [key, { target }])),
  },
});
console.log("OWNED_AI_PREVIEW_READY");
const input = createInterface({ input: process.stdin });
await new Promise((done) => { input.once("line", done); input.once("close", done); });
await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
input.close();
