import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { CreatedProjectUploadIntent } from "./documentUploadIntentClient";

export interface ReceivedProjectUploadContent {
  readonly uploadId: string;
  readonly sizeBytes: number;
  readonly sha256: string;
  readonly detectedMime: string;
}

const messages = {
  DOCUMENT_UPLOAD_CONTENT_INVALID: "上传文件或上传意图无效。",
  DOCUMENT_UPLOAD_HASH_UNAVAILABLE: "无法计算文件摘要，请换用受支持的安全浏览器环境。",
  AUTH_RELOGIN_REQUIRED: "上传文件前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许上传文档。",
  RESOURCE_NOT_FOUND: "上传意图不存在或无权使用。",
  PROJECT_ARCHIVED: "项目已归档，不允许上传。",
  CONFLICT_STATE: "当前上传状态不允许接收文件。",
  FILE_UPLOAD_EXPIRED: "上传意图已过期或终止。",
  FILE_TOO_LARGE: "文件超过允许大小。",
  FILE_TYPE_UNSUPPORTED: "不支持此文件类型。",
  FILE_INTEGRITY_MISMATCH: "文件内容与声明的摘要不一致。",
  DOCUMENT_UPLOAD_CONTENT_UNCERTAIN: "无法确认文件内容是否已接收，请勿自动重传。",
} as const;
export type DocumentUploadContentErrorCode = keyof typeof messages;
export class DocumentUploadContentError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: DocumentUploadContentErrorCode) {
    super(messages[code]);
    this.name = "DocumentUploadContentError";
    this.uncertain = code === "DOCUMENT_UPLOAD_CONTENT_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const token = /^[A-Za-z0-9_-]{43}$/;
const sha256 = /^[0-9a-f]{64}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function future(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && parsed > Date.now()
    && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
function validIntent(value: unknown): value is CreatedProjectUploadIntent {
  return record(value) && identifier(value.uploadId)
    && typeof value.uploadToken === "string" && token.test(value.uploadToken)
    && future(value.expiresAt);
}
function mime(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 255
    && value.trim() === value && !/\p{C}/u.test(value);
}

export class DocumentUploadContentClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_INVALID");
  }

  async putProject(projectId: string, intent: CreatedProjectUploadIntent,
    content: Blob): Promise<ReceivedProjectUploadContent> {
    if (!identifier(projectId) || !validIntent(intent) || !(content instanceof Blob)
      || !Number.isSafeInteger(content.size) || content.size < 1 || content.size > 100_000_000) {
      throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_INVALID");
    }
    let digest: string;
    try {
      if (!globalThis.crypto?.subtle?.digest) throw new Error("Web Crypto unavailable");
      const bytes = await content.arrayBuffer();
      if (bytes.byteLength !== content.size) throw new Error("Blob size changed");
      const hash = await globalThis.crypto.subtle.digest("SHA-256", bytes);
      if (hash.byteLength !== 32) throw new Error("Invalid digest length");
      digest = Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join("");
    } catch {
      throw new DocumentUploadContentError("DOCUMENT_UPLOAD_HASH_UNAVAILABLE");
    }
    if (!future(intent.expiresAt)) throw new DocumentUploadContentError("FILE_UPLOAD_EXPIRED");
    let response: Response;
    try {
      response = await this.session.putProjectDocumentUploadContent(
        projectId, intent.uploadId, intent.uploadToken, digest, content);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new DocumentUploadContentError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new DocumentUploadContentError("AUTH_CLIENT_BUSY");
      }
      throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409,
          CONFLICT_STATE: 409, FILE_UPLOAD_EXPIRED: 409, FILE_TOO_LARGE: 413,
          FILE_TYPE_UNSUPPORTED: 415, FILE_INTEGRITY_MISMATCH: 409,
          VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new DocumentUploadContentError(code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
            ? "DOCUMENT_UPLOAD_CONTENT_INVALID" : code as DocumentUploadContentErrorCode);
        }
        throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_UNCERTAIN");
      }
      const data = payload.data;
      if (!record(data) || data.upload_id !== intent.uploadId || data.size_bytes !== content.size
        || data.sha256 !== digest || !mime(data.detected_mime)
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) {
        throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_UNCERTAIN");
      }
      return Object.freeze({ uploadId: intent.uploadId, sizeBytes: content.size,
        sha256: digest, detectedMime: data.detected_mime });
    } catch (failure) {
      if (failure instanceof DocumentUploadContentError) throw failure;
      throw new DocumentUploadContentError("DOCUMENT_UPLOAD_CONTENT_UNCERTAIN");
    }
  }
}
