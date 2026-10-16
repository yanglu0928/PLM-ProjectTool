# SurveyVersion 原子送审 HTTP V1 增量

日期：2026-10-06。实现基线：冻结 API-01/API-04、Schema 0106、CR-SUR-001/005 与已验证 PROJECT Review 内核。

## Operation

`POST /api/v1/projects/{project_id}/surveys/{survey_id}/versions/{survey_version_id}:submit-review`

Router 只通过 `create_app(survey_review_submission_router=...)` 显式注入，默认应用返回 404；Windows 生产组合留 `SUR-01-A05-A07`。

请求正文必须精确包含：

```json
{
  "reviewer_ids": ["canonical-lowercase-uuid"],
  "policy_ref": "SURVEY_ALL_V1",
  "due_at": null,
  "submission_note": null
}
```

`reviewer_ids` 为 1～32 个不重复规范 UUID，服务端按 UUID 文本规范排序后形成幂等指纹；Policy 固定为 `SURVEY_ALL_V1`。依据 CR-SUR-005，当前通用 Review Schema 不持久化 `due_at` 与 `submission_note`，V1 非空值明确返回 422，不得静默丢弃。

## 安全、事务与响应

要求可信 Origin/Host、当前 `plm_session`、`X-CSRF-Token`、有效 License 和 16～128 字符可打印 ASCII `Idempotency-Key`。仅当前 ACTIVE Project 的 ProjectManager 可送审；评审人、Survey/Version 身份、DRAFT 状态、完整问题快照、四类来源和目标部门均在 Owner 事务内重验。

一次调用在同一事务中创建 PROJECT Review、启动第1轮、关联 `SRV-02 + SURVEY_ALL_V1`、把 SurveyVersion 推进到 `IN_REVIEW`、写 Audit 和持久幂等回执。成功返回 201、`Cache-Control: no-store`、Review 强 ETag，以及 Review/Round/Survey/Version、规范评审人、提交人和提交时间；不返回跨模块正文、路径或内部异常。

同 Key 同载荷恢复首次 Review/Round，不创建第二份 Review；重放仍重验当前 Project 授权和 Survey Subject 访问。死锁最多重试三次，耗尽后安全返回 503。

## 错误、兼容与回滚

权限或隔离失败对资源投影 404；License 403；非法请求、Policy、可选元数据或当前定义 422；幂等、版本或 Subject 锁冲突 409；未知内部失败 503。无 Schema/Migration/依赖/配置/Secret、网络或外发变化。停止注入 Router 即回滚公开入口，既有 Review、Survey、Audit 和回执历史保留。
