import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { ReceivedProjectUploadContent } from "./documentUploadContentClient";

export type ProjectUploadCommitTarget =
  | Readonly<{ kind: "NEW" }>
  | Readonly<{ kind: "VERSION"; documentId: string; parentEtag: string }>;

export interface ProjectUploadCommitFirstReceipt {
  readonly first_result: Readonly<{
    uploadId: string;
    documentId: string;
    documentVersionId: string;
    versionNo: number;
    parseJobId: string;
  }>;
  /** An idempotent replay proves the first result, not the current Document state. */
  readonly is_current_state_proof: false;
}

export interface ProjectUploadAbortFirstReceipt {
  readonly first_result: Readonly<{ uploadId: string; state: "ABORTED"; cleanupPending: boolean }>;
  readonly is_current_state_proof: false;
}

const messages = {
  DOCUMENT_UPLOAD_FINALIZE_INVALID: "请重新核对上传意图、内容及文档原版本。",
  AUTH_RELOGIN_REQUIRED: "提交上传前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许此操作。",
  RESOURCE_NOT_FOUND: "上传意图不存在或无权操作。",
  PROJECT_ARCHIVED: "项目已归档，不允许提交上传。",
  CONFLICT_VERSION: "文档版本已变化，请重新读取后决定。",
  CONFLICT_STATE: "上传状态已变化，请重新读取后决定。",
  CONFLICT_IDEMPOTENCY: "原操作标识与本次请求不一致，已停止重试。",
  FILE_UPLOAD_EXPIRED: "上传意图已过期或终止。",
  FILE_INTEGRITY_MISMATCH: "上传文件完整性校验失败。",
  DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN: "无法确认提交结果；请保留原操作标识并核对文档历史。",
} as const;
export type DocumentUploadFinalizeErrorCode = keyof typeof messages;
export class DocumentUploadFinalizeError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: DocumentUploadFinalizeErrorCode) {
    super(messages[code]);
    this.name = "DocumentUploadFinalizeError";
    this.uncertain = code === "DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const sha256 = /^[0-9a-f]{64}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function parentEtag(value: unknown): value is string {
  return typeof value === "string" && /^"v(?:0|[1-9]\d*)"$/.test(value)
    && Number.isSafeInteger(Number(value.slice(2, -1)))
    && Number(value.slice(2, -1)) < Number.MAX_SAFE_INTEGER;
}
function key(value: unknown): value is string {
  return typeof value === "string" && /^[\x20-\x7e]{16,128}$/.test(value);
}
function safeContent(value: unknown): value is ReceivedProjectUploadContent {
  return record(value) && identifier(value.uploadId)
    && typeof value.sizeBytes === "number" && Number.isSafeInteger(value.sizeBytes)
    && value.sizeBytes > 0 && value.sizeBytes <= 100_000_000
    && typeof value.sha256 === "string" && sha256.test(value.sha256)
    && typeof value.detectedMime === "string" && value.detectedMime.length > 0
    && value.detectedMime.length <= 255 && value.detectedMime.trim() === value.detectedMime
    && !/\p{C}/u.test(value.detectedMime);
}
function targetEtag(target: ProjectUploadCommitTarget): string | null {
  if (!record(target)) throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_INVALID");
  if (target.kind === "NEW" && Object.keys(target).length === 1) return null;
  if (target.kind === "VERSION" && Object.keys(target).length === 3
    && identifier(target.documentId) && parentEtag(target.parentEtag)) return target.parentEtag;
  throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_INVALID");
}

export class DocumentUploadFinalizeClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_INVALID");
  }

  async #payload(response: Response, successStatus: number): Promise<Record<string, unknown>> {
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
      }
      if (response.status !== successStatus) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409,
          CONFLICT_VERSION: 409, CONFLICT_STATE: 409, CONFLICT_IDEMPOTENCY: 409,
          FILE_UPLOAD_EXPIRED: 409, FILE_INTEGRITY_MISMATCH: 409,
          CONFLICT_VERSION_REQUIRED: 428, VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400 };
        if (typeof code === "string" && Object.hasOwn(known, code) && response.status === known[code]) {
          throw new DocumentUploadFinalizeError(["CONFLICT_VERSION_REQUIRED", "VALIDATION_FAILED",
            "REQUEST_MALFORMED"].includes(code) ? "DOCUMENT_UPLOAD_FINALIZE_INVALID" : code as DocumentUploadFinalizeErrorCode);
        }
        throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
      }
      if (!/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")
        || !record(payload.data)) {
        throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
      }
      return payload.data;
    } catch (failure) {
      if (failure instanceof DocumentUploadFinalizeError) throw failure;
      throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
    }
  }

  async commitProject(projectId: string, content: ReceivedProjectUploadContent,
    target: ProjectUploadCommitTarget, idempotencyKey: string): Promise<ProjectUploadCommitFirstReceipt> {
    if (!identifier(projectId) || !safeContent(content) || !key(idempotencyKey)) {
      throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_INVALID");
    }
    const etag = targetEtag(target);
    let response: Response;
    try {
      response = await this.session.postProjectDocumentUploadCommit(
        projectId, content.uploadId, idempotencyKey, etag);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new DocumentUploadFinalizeError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new DocumentUploadFinalizeError("AUTH_CLIENT_BUSY");
      }
      throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
    }
    const data = await this.#payload(response, 201);
    if (data.upload_id !== content.uploadId || !identifier(data.document_id)
      || !identifier(data.document_version_id) || !identifier(data.parse_job_id)
      || typeof data.version_no !== "number" || !Number.isSafeInteger(data.version_no)
      || data.version_no < 1 || (target.kind === "VERSION" && data.document_id !== target.documentId)
      || response.headers.get("location") !== `/api/v1/projects/${projectId}/documents/${data.document_id}/versions/${data.document_version_id}`) {
      throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
    }
    return Object.freeze({ first_result: Object.freeze({ uploadId: content.uploadId,
      documentId: data.document_id, documentVersionId: data.document_version_id,
      versionNo: data.version_no, parseJobId: data.parse_job_id }), is_current_state_proof: false as const });
  }

  async abortProject(projectId: string, uploadId: string,
    idempotencyKey: string): Promise<ProjectUploadAbortFirstReceipt> {
    if (!identifier(projectId) || !identifier(uploadId) || !key(idempotencyKey)) {
      throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_INVALID");
    }
    let response: Response;
    try {
      response = await this.session.postProjectDocumentUploadAbort(projectId, uploadId, idempotencyKey);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new DocumentUploadFinalizeError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new DocumentUploadFinalizeError("AUTH_CLIENT_BUSY");
      }
      throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
    }
    const data = await this.#payload(response, 200);
    if (data.upload_id !== uploadId || data.state !== "ABORTED" || typeof data.cleanup_pending !== "boolean") {
      throw new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN");
    }
    return Object.freeze({ first_result: Object.freeze({ uploadId, state: "ABORTED" as const,
      cleanupPending: data.cleanup_pending }), is_current_state_proof: false as const });
  }
}
