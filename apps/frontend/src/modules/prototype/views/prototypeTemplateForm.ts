import type { PrototypeTemplateView } from "@/modules/prototype/api/prototypeReadClient";
import type { PrototypeTemplateContentInput } from "@/modules/prototype/api/prototypeWriteClient";

export const prototypeTemplateLayouts = Object.freeze([
  { value: "SINGLE_COLUMN", label: "单列" },
  { value: "TWO_COLUMN", label: "双列" },
  { value: "MASTER_DETAIL", label: "主从" },
  { value: "DASHBOARD", label: "看板" },
]);
export const prototypeTemplateComponents = Object.freeze(["FORM", "TABLE", "NAVIGATION", "PREVIEW", "SUMMARY"]);
export const prototypeTemplateTerminals = Object.freeze(["DESKTOP", "TABLET", "WEB"]);

export interface PrototypeTemplateEditorState {
  readonly layout: string;
  readonly components: readonly string[];
  readonly terminals: readonly string[];
  readonly artifactVersions: readonly string[];
}

export function canonicalPrototypeTemplate(item: PrototypeTemplateView): { readonly layout: string;
  readonly components: readonly string[] } | null {
  const layout = item.layout_contract.layout; const values = new Set(prototypeTemplateLayouts.map(option => option.value));
  const raw = item.component_contract.components;
  if (typeof layout !== "string" || !values.has(layout) || !Array.isArray(raw)) return null;
  const components = raw.map(value => typeof value === "object" && value !== null && !Array.isArray(value)
    && Object.keys(value).length === 1 && typeof (value as { kind?: unknown }).kind === "string"
    ? (value as { kind: string }).kind : "");
  if (!components.length || components.some(value => !prototypeTemplateComponents.includes(value))) return null;
  return Object.freeze({ layout, components: Object.freeze(components) });
}

export function prototypeTemplateContent(state: PrototypeTemplateEditorState): PrototypeTemplateContentInput {
  const components = [...new Set(state.components)].sort(); const terminals = [...new Set(state.terminals)].sort();
  const artifacts = [...new Set(state.artifactVersions)].sort()
    .map(target_id => Object.freeze({ artifact_kind: "DOCUMENT_VERSION" as const, target_id }));
  return Object.freeze({ layout_contract: Object.freeze({ layout: state.layout }),
    component_contract: Object.freeze({ components: Object.freeze(components.map(kind => Object.freeze({ kind }))) }),
    applicable_terminals: Object.freeze(terminals), artifact_refs: Object.freeze(artifacts) });
}
