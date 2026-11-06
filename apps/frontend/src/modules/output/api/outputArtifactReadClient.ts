/** Strict same-origin reference reader for an available generated artifact. */
export type ArtifactKind = "DOCX" | "PPTX" | "PNG" | "JPEG";

export interface OutputArtifactReference {
  readonly output_artifact_id: string;
  readonly output_request_id: string;
  readonly project_id: string;
  readonly document_id: string;
  readonly document_version_id: string;
  readonly artifact_kind: ArtifactKind;
  readonly media_type: string;
  readonly content_sha256: string;
  readonly size_bytes: number;
  readonly content_url: string;
}

const messages = {
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许下载此输出文件。",
  RESOURCE_NOT_FOUND: "输出文件尚未可用或无权读取。",
  OUTPUT_ARTIFACT_UNAVAILABLE: "暂时无法获取输出文件，请稍后重试。",
} as const;
export type OutputArtifactReadErrorCode = keyof typeof messages;
export class OutputArtifactReadError extends Error {
  constructor(readonly code: OutputArtifactReadErrorCode) {
    super(messages[code]);
    this.name = "OutputArtifactReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const mimeByKind: Readonly<Record<ArtifactKind, string>> = {
  DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  PNG: "image/png",
  JPEG: "image/jpeg",
};
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function fail(): never { throw new OutputArtifactReadError("OUTPUT_ARTIFACT_UNAVAILABLE"); }

export function parseOutputArtifactReference(
  value: unknown, projectId: string, requestId: string,
): OutputArtifactReference {
  const fields = [
    "output_artifact_id", "output_request_id", "project_id", "document_id",
    "document_version_id", "artifact_kind", "media_type", "content_sha256",
    "size_bytes", "content_url",
  ] as const;
  if (!id(projectId) || !id(requestId) || !record(value) || !exact(value, fields)
    || !id(value.output_artifact_id) || value.output_request_id !== requestId
    || value.project_id !== projectId || !id(value.document_id)
    || !id(value.document_version_id)
    || !["DOCX", "PPTX", "PNG", "JPEG"].includes(value.artifact_kind as string)
    || value.media_type !== mimeByKind[value.artifact_kind as ArtifactKind]
    || typeof value.content_sha256 !== "string" || !digest.test(value.content_sha256)
    || !Number.isSafeInteger(value.size_bytes)
    || (value.size_bytes as number) < 0 || (value.size_bytes as number) > 134217728
    || value.content_url !== (
      "/api/v1/projects/" + projectId + "/documents/" + value.document_id
      + "/versions/" + value.document_version_id + "/content"
    )) fail();
  return Object.freeze({
    output_artifact_id: value.output_artifact_id,
    output_request_id: requestId,
    project_id: projectId,
    document_id: value.document_id,
    document_version_id: value.document_version_id,
    artifact_kind: value.artifact_kind as ArtifactKind,
    media_type: value.media_type as string,
    content_sha256: value.content_sha256,
    size_bytes: value.size_bytes as number,
    content_url: value.content_url as string,
  });
}

export class OutputArtifactReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
              private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new OutputArtifactReadError("OUTPUT_ARTIFACT_UNAVAILABLE");
    }
  }

  async get(projectId: string, requestId: string): Promise<OutputArtifactReference> {
    if (!id(projectId) || !id(requestId)) fail();
    const data = await this.getJson(
      "/api/v1/projects/" + projectId + "/output-requests/" + requestId + "/artifact",
    );
    return parseOutputArtifactReference(data, projectId, requestId);
  }

  private async getJson(path: string): Promise<unknown> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
          !== "application/json") fail();
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload)
        || typeof payload.trace_id !== "string" || !uuid.test(payload.trace_id)) fail();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404,
        };
        if (typeof code === "string" && expected[code] === response.status) {
          throw new OutputArtifactReadError(code as OutputArtifactReadErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"])) fail();
      return payload.data;
    } catch (error) {
      if (error instanceof OutputArtifactReadError) throw error;
      return fail();
    } finally {
      window.clearTimeout(timer);
    }
  }
}
