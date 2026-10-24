/** Same canonical fixed-version collection identity as the frozen Capability domain. */
export async function capabilitySourceCollectionRef(versionIds: readonly string[]): Promise<string> {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  if (!Array.isArray(versionIds) || versionIds.length < 1 || versionIds.length > 500
    || versionIds.some(id => typeof id !== "string" || !uuid.test(id)
      || id === "00000000-0000-0000-0000-000000000000")
    || new Set(versionIds).size !== versionIds.length) throw new Error("固定来源集合无效。");
  const payload = new TextEncoder().encode(`capability-source-set.v1\n${[...versionIds].sort().join("\n")}`);
  const digest = await crypto.subtle.digest("SHA-256", payload);
  return `sha256:${[...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("")}`;
}
