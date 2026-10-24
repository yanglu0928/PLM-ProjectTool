import { describe, expect, it } from "vitest";
import { capabilitySourceCollectionRef } from "./capabilitySourceCollection";

const a = "01234567-89ab-4cde-8123-456789abcdef";
const b = "11234567-89ab-4cde-8123-456789abcdef";
describe("capabilitySourceCollectionRef", () => {
  it("is order-independent and matches the frozen source-set identity", async () => {
    const first = await capabilitySourceCollectionRef([a, b]);
    expect(first).toBe("sha256:9f5c9a2e244c880199cc9b1835ce1847ceac013fefdc2737dd41c6f4d2477091");
    expect(await capabilitySourceCollectionRef([b, a])).toBe(first);
    expect(await capabilitySourceCollectionRef([a])).not.toBe(first);
  });
  it("fails closed for duplicate or malformed fixed versions", async () => {
    await expect(capabilitySourceCollectionRef([a, a])).rejects.toThrow();
    await expect(capabilitySourceCollectionRef([])).rejects.toThrow();
    await expect(capabilitySourceCollectionRef(["other"])).rejects.toThrow();
  });
});
