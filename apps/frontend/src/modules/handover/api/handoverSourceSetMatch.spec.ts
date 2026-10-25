import { describe, expect, it } from "vitest";
import { canonicalHandoverSourceSetRef, HandoverSourceSetError,
  matchesHandoverSourceSet } from "./handoverSourceSetMatch";

const documentA = "11234567-89ab-4cde-8123-456789abcdef";
const documentB = "41234567-89ab-4cde-8123-456789abcdef";
const versionA = "21234567-89ab-4cde-8123-456789abcdef";
const versionB = "31234567-89ab-4cde-8123-456789abcdef";
const expected = "sha256:5d079216a7c79d5da45ce91d9a80a60cd319b5da9a01a646038065cfa5d65c26";
const digest = async (payload: Uint8Array<ArrayBuffer>) => {
  expect(new TextDecoder().decode(payload)).toBe(
    `handover-source-set.v1\n${versionA}\n${versionB}`,
  );
  return Uint8Array.from(expected.slice(7).match(/../g)!.map(part => Number.parseInt(part, 16))).buffer;
};
const sources = [{ document_id: documentA, document_version_id: versionA },
  { document_id: documentB, document_version_id: versionB }];

describe("Handover source set match", () => {
  it("matches the backend two-version vector regardless of selection order", async () => {
    await expect(canonicalHandoverSourceSetRef(sources, digest)).resolves.toBe(expected);
    await expect(matchesHandoverSourceSet([...sources].reverse(), expected, digest)).resolves.toBe(true);
    const other = async (_payload: Uint8Array<ArrayBuffer>) => new Uint8Array(32).buffer;
    await expect(matchesHandoverSourceSet(sources.slice(0, 1), expected, other)).resolves.toBe(false);
  });

  it("rejects empty, duplicate, malformed or noncanonical references", async () => {
    await expect(canonicalHandoverSourceSetRef([], digest)).rejects.toBeInstanceOf(HandoverSourceSetError);
    await expect(canonicalHandoverSourceSetRef([sources[0]!, sources[0]!], digest))
      .rejects.toBeInstanceOf(HandoverSourceSetError);
    await expect(matchesHandoverSourceSet(sources, expected.toUpperCase(), digest))
      .rejects.toBeInstanceOf(HandoverSourceSetError);
  });

  it("fails closed when hashing is unavailable", async () => {
    await expect(canonicalHandoverSourceSetRef(sources, async () => new ArrayBuffer(0)))
      .rejects.toBeInstanceOf(HandoverSourceSetError);
  });
});
