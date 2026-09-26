# Audit Export Read V1 增量契约

版本：V1-INCREMENT-1；日期：2026-09-26；依据：CR-AUD-003。原 API-CONTRACT-CANDIDATE-V1 / 64cdf09 保留。

|方法|路径|权限|响应|
|---|---|---|---|
|GET|`/api/v1/projects/{project_id}/audit-exports/{export_id}`|当前有效 Session、License、实际项目 PM|200 结果详情|
|GET|`/api/v1/admin/audit-exports/{export_id}`|当前有效 Session、License、部署 Admin，仅 DEPLOYMENT|200 结果详情|
|GET|上述详情路径追加 `/content`|同上，复制后再次授权|200 完整 JSONL 附件|

详情 envelope 为 `data` 和 `trace_id`。data 唯一字段：`export_id`、`scope`（PROJECT/DEPLOYMENT）、`project_id`（部署为 null）、`published_at`（UTC ISO8601 Z）、`size_bytes`、`mime_type`（application/x-ndjson）、`file_sha256`（64 位小写 hex）、`manifest_version`、`manifest_sha256`（64 位小写 hex）。仅已发布成功结果，未完成/缺来源/跨 Scope 404；不是 Job 状态查询，也不因详情成功证明物理文件完好。

禁止返回原始 manifest、FileId/Locator、render_attempt_id、Worker/Lease/fencing、发布 AuditId、原提交者、Session 或签名密钥。metadata 无业务写。各 GET 不接受 query 参数；可信 Host 和严格唯一 Cookie 必须通过，不使用 GET CSRF 写 token。零 UUID 404；畸形 UUID 422。Project Admin 仍须实际 PM，不继承部署身份。

错误统一 envelope：AUTH_SESSION_EXPIRED 401、AUTH_CSRF_INVALID 403、LICENSE_OPERATION_DENIED 403、RESOURCE_NOT_FOUND 404、VALIDATION_FAILED 422、REQUEST_MALFORMED 400、SYSTEM_UNAVAILABLE 503。内容不可读/损坏映射 FILE_CONTENT_UNAVAILABLE 503，不泄漏底层路径或异常；授权失败不能产生文件失败审计。

内容为原始 UTF-8 JSONL（二进制响应不套 JSON envelope），固定安全附件名 `audit-export-{export_id}.jsonl`；Content-Length、Content-Type、nosniff、no-store。不支持 Range/If-Range，返回 REQUEST_MALFORMED。真实快照完整 Hash、128MiB 上限，返回字节前重核当前 Session/权限。准备到传输占有有界槽，满额 503；正常结束、断连、取消或异常关闭快照并释放槽。HTTP 开始后失败终止传输，不伪造成功 JSON。

实现与验收分阶段；本文件不代表上述全部路由已可用。默认应用无路由，生产组合待实际验收后显式启用。

实施状态（2026-09-26）：P01详情/P02内容opt-in Router及真实PG来源+文件验证PASS；普通create_app仍404。下载名额仅进程内Router实例有界（默认4、配置1～20），不是跨进程全局并发承诺；准备/读取消保留活跃线程名额直至实际线程结束，防止遗留工作无限扩张。生产Windows组合、真实代理和三平台/性能仍待。

P03（2026-09-26）：`--platform` / `--platform-write` 两Windows显式组合已挂载四GET，真实数据库/文件与合成信任源验证PASS；默认/仅登录不挂载，提交导出POST仍未开放。正式信任材料/目标账户/真实代理/三平台/性能未验，不能据此宣布正式安装包完成。
