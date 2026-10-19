# SOL_SPEC_SUBMIT_REVIEW V1 增量合同

日期：2026-10-19。状态：`SOL-06-A14-P06` 合同实现；Windows 生产组合尚未装配。

## 路径与权限

`POST /api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:submit-review`

- 仅当前 ACTIVE 项目的 `PROJECT_MANAGER` 可调用；需有效 Session、CSRF、License 和 `Idempotency-Key`。
- `spec_id` 是固定 StructuredSolutionSpec 版本。`spec_series_id` 由服务端同事务解析并作为 `SOL-06` Review Subject，不是请求字段。
- Router 为 opt-in；默认 `create_app()` 不挂载，返回 404。

## 请求

```json
{
  "reviewer_ids": ["00000000-0000-0000-0000-000000000001"],
  "policy_ref": "STRUCTURED_SPEC_ALL_V1",
  "due_at": null,
  "submission_note": null
}
```

请求必须精确包含上述四字段。Reviewer 为 1～32 个互异 canonical lowercase non-zero UUID，服务端规范排序并按当前项目成员资格重验。当前 Review Schema 不保存 `due_at` 与 `submission_note`，V1 因此只接受显式 `null`；非空返回 422，不静默丢弃。

## 成功响应

成功为 201，`Cache-Control: no-store`，`ETag: "v1"`。`data` 精确包含：

- `review_id`、`review_round_id`、`subject_type=SOL-06`、`project_id`；
- 服务端派生的 `spec_series_id` 与路径绑定的 `structured_solution_spec_id`；
- `policy_ref=STRUCTURED_SPEC_ALL_V1`、规范排序的 `reviewer_ids`；
- `state=IN_REVIEW`、`round_no=1`、`review_etag="v1"`；
- `submitted_by`、UTC `submitted_at`。

外层 `trace_id` 与响应 `X-Trace-Id` 表示本次 HTTP 请求。同 Key、同请求在当前访问复验后恢复首次 201 Review/Round，不创建第二轮。

## 失败边界

- 非法 Origin/CSRF/Session、非规范 UUID、未知或缺失字段、查询参数、错误 Content-Type/JSON 失败关闭。
- 当前版本不是最新就绪 DRAFT、来源/Trace/类型声明不再满足条件时为 422；Reviewer 不合格为 422。
- 同 Key 请求漂移、版本冲突、Subject 已锁或项目已归档为 409；License 为 403；隐藏资源/权限为 404；内部不一致为 503。
- 所有错误响应均为统一错误信封与 `no-store`，不返回异常文本、Traceback、Session、CSRF 或幂等摘要。
