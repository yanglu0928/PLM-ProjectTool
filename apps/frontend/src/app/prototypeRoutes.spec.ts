import { createMemoryHistory } from "vue-router";
import { describe, expect, it } from "vitest";

import { createAppRouter } from "@/app/router";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const prototypeId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef";

describe("Prototype application routes", () => {
  it.each([
    ["project-prototypes", `/projects/${projectId}/prototypes`, { projectId }],
    ["project-prototype-detail", `/projects/${projectId}/prototypes/${prototypeId}`, { projectId, prototypeId }],
    ["project-prototype-versions", `/projects/${projectId}/prototypes/${prototypeId}/versions`, { projectId, prototypeId }],
    ["project-prototype-version-detail", `/projects/${projectId}/prototypes/${prototypeId}/versions/${versionId}`,
      { projectId, prototypeId, versionId }],
    ["project-prototype-packages", `/projects/${projectId}/prototype-packages`, { projectId }],
    ["project-prototype-templates", `/projects/${projectId}/prototype-templates`, { projectId }],
    ["project-prototype-links", `/projects/${projectId}/prototype-links`, { projectId }],
    ["global-prototype-templates", "/admin/prototype-templates", {}],
  ] as const)("resolves %s without falling through to 404", (name, path, params) => {
    const router = createAppRouter(createMemoryHistory()); const byName = router.resolve({ name, params });
    expect(byName.href).toBe(path); expect(byName.matched.at(-1)?.name).toBe(name);
    expect(router.resolve(path).name).toBe(name);
  });
});
