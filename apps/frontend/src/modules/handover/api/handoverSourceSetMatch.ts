/** Client-side preview of the frozen Handover source-set identity; server validation remains authoritative. */
import { normalizeHandoverSources, type HandoverCreateSource } from "./handoverCreateClient";

const refPattern = /^sha256:[0-9a-f]{64}$/;
export class HandoverSourceSetError extends Error {
  constructor() { super("固定文档集合无法核对；请重新选择原分析的文档版本。");
    this.name = "HandoverSourceSetError"; }
}
type Digest = (payload: Uint8Array<ArrayBuffer>) => Promise<ArrayBuffer>;
const browserDigest: Digest = payload => globalThis.crypto.subtle.digest("SHA-256", payload);

export async function canonicalHandoverSourceSetRef(sources: readonly HandoverCreateSource[],
  digest: Digest = browserDigest): Promise<string> {
  let normalized: readonly HandoverCreateSource[];
  try { normalized = normalizeHandoverSources(sources); } catch { throw new HandoverSourceSetError(); }
  if (typeof digest !== "function") throw new HandoverSourceSetError();
  const payload = "handover-source-set.v1\n"
    + normalized.map(source => source.document_version_id).sort().join("\n");
  try {
    const result = await digest(new TextEncoder().encode(payload));
    if (Object.prototype.toString.call(result) !== "[object ArrayBuffer]" || result.byteLength !== 32) {
      throw new Error("digest unavailable");
    }
    return "sha256:" + Array.from(new Uint8Array(result), byte => byte.toString(16).padStart(2, "0")).join("");
  } catch { throw new HandoverSourceSetError(); }
}

export async function matchesHandoverSourceSet(sources: readonly HandoverCreateSource[],
  expected: string, digest: Digest = browserDigest): Promise<boolean> {
  if (typeof expected !== "string" || !refPattern.test(expected)) throw new HandoverSourceSetError();
  return await canonicalHandoverSourceSetRef(sources, digest) === expected;
}
