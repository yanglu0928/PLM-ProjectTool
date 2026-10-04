import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

type CommonInput = Readonly<{
  purpose: string;
  displayName: string;
  sizeHintBytes?: number;
  mimeHint?: string;
}>;
export type ProjectUploadIntentInput = CommonInput & (
  Readonly<{ kind: "NEW"; category: string; subtype?: string; documentPurpose?: string; title: string }> |
  Readonly<{ kind: "VERSION"; documentId: string; supersedesVersionId?: string }>
);
export interface CreatedProjectUploadIntent {
  readonly uploadId: string;
  /** Short-lived bearer proof: keep only in memory, never log or persist. */
  readonly uploadToken: string;
  readonly expiresAt: string;
}

const messages = {
  DOCUMENT_UPLOAD_INVALID_INPUT: "请检查文档类型、名称和文件信息。",
  AUTH_RELOGIN_REQUIRED: "上传文档前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许上传文档。",
  RESOURCE_NOT_FOUND: "文档不存在或无权上传。",
  PROJECT_ARCHIVED: "项目已归档，不允许上传。",
  CONFLICT_STATE: "当前文档状态不允许上传。",
  CONFLICT_VERSION: "文档版本已变化，请刷新。",
  CONFLICT_IDEMPOTENCY: "原操作标识与本次输入不一致，已停止重试。",
  FILE_UPLOAD_EXPIRED: "上传意图已过期或已终止。",
  DOCUMENT_UPLOAD_CREATE_UNCERTAIN: "无法确认上传意图是否已建立，请勿换操作标识重试。",
} as const;
export type DocumentUploadIntentErrorCode = keyof typeof messages;
export class DocumentUploadIntentError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: DocumentUploadIntentErrorCode) {
    super(messages[code]);
    this.name = "DocumentUploadIntentError";
    this.uncertain = code === "DOCUMENT_UPLOAD_CREATE_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const token = /^[A-Za-z0-9_-]{43}$/;
const purpose = /^[A-Z][A-Z0-9_]{0,63}$/;
const categories = new Set(["CONTRACTUAL", "PROJECT_RECORD", "STANDARD_CAPABILITY",
  "REFERENCE_MATERIAL", "TEMPLATE", "OTHER"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function label(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max
    && value.trim() === value && !/\p{C}/u.test(value);
}
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && parsed > Date.now()
    && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
function prepared(input: ProjectUploadIntentInput): string {
  if (!record(input) || !purpose.test(input.purpose) || !label(input.displayName, 255)
    || (input.sizeHintBytes !== undefined && (!Number.isSafeInteger(input.sizeHintBytes)
      || input.sizeHintBytes < 0 || input.sizeHintBytes > 100_000_000))
    || (input.mimeHint !== undefined && !label(input.mimeHint, 255))) {
    throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_INVALID_INPUT");
  }
  const body: Record<string, unknown> = { purpose: input.purpose, display_name: input.displayName };
  if (input.sizeHintBytes !== undefined) body.size_hint_bytes = input.sizeHintBytes;
  if (input.mimeHint !== undefined) body.mime_hint = input.mimeHint;
  if (input.kind === "NEW") {
    if (!categories.has(input.category) || !label(input.title, 255)
      || (input.subtype !== undefined && !label(input.subtype, 128))
      || (input.documentPurpose !== undefined && !label(input.documentPurpose, 255))
      || (input.category === "OTHER" && (input.subtype === undefined || input.documentPurpose === undefined))
      || Object.keys(input).some((key) => !["kind", "purpose", "displayName", "sizeHintBytes", "mimeHint",
        "category", "subtype", "documentPurpose", "title"].includes(key))) {
      throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_INVALID_INPUT");
    }
    body.category = input.category;
    body.title = input.title;
    if (input.subtype !== undefined) body.subtype = input.subtype;
    if (input.documentPurpose !== undefined) body.document_purpose = input.documentPurpose;
  } else if (input.kind === "VERSION") {
    if (!identifier(input.documentId) || (input.supersedesVersionId !== undefined
      && !identifier(input.supersedesVersionId))
      || Object.keys(input).some((key) => !["kind", "purpose", "displayName", "sizeHintBytes", "mimeHint",
        "documentId", "supersedesVersionId"].includes(key))) {
      throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_INVALID_INPUT");
    }
    body.document_id = input.documentId;
    if (input.supersedesVersionId !== undefined) body.supersedes_version_id = input.supersedesVersionId;
  } else {
    throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_INVALID_INPUT");
  }
  return JSON.stringify(body);
}

export class DocumentUploadIntentClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_INVALID_INPUT");
  }

  async createProject(projectId: string, input: ProjectUploadIntentInput,
    idempotencyKey: string): Promise<CreatedProjectUploadIntent> {
    if (!identifier(projectId) || typeof idempotencyKey !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_INVALID_INPUT");
    }
    const body = prepared(input);
    let response: Response;
    try {
      response = await this.session.postProjectDocumentUploadCreate(projectId, body, idempotencyKey);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new DocumentUploadIntentError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new DocumentUploadIntentError("AUTH_CLIENT_BUSY");
      }
      throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN");
      }
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409,
          CONFLICT_STATE: 409, CONFLICT_VERSION: 409, CONFLICT_IDEMPOTENCY: 409,
          FILE_UPLOAD_EXPIRED: 409, VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new DocumentUploadIntentError(code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
            ? "DOCUMENT_UPLOAD_INVALID_INPUT" : code as DocumentUploadIntentErrorCode);
        }
        throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN");
      }
      const data = payload.data;
      if (!record(data) || !identifier(data.upload_id) || typeof data.upload_token !== "string"
        || !token.test(data.upload_token) || !instant(data.expires_at)
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/document-uploads/${data.upload_id}`
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) {
        throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN");
      }
      return Object.freeze({ uploadId: data.upload_id, uploadToken: data.upload_token, expiresAt: data.expires_at });
    } catch (failure) {
      if (failure instanceof DocumentUploadIntentError) throw failure;
      throw new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN");
    }
  }
}
