# GLOBAL Reference 候选发布管理员命令 `/api/v1` 增量

日期：2026-10-09。来源：Gate 2 API-04 的 GLOBAL Reference/OutlineVersion 固定引用规则 → CR-SOL-018 → DEC-1148～1150 → `SOL-03-A04-P03-P03-P06-A03-P03`。本增量新增默认关闭的管理命令，不修改任何已冻结路径或项目角色。

`POST /api/v1/global/reference-solutions/{reference_solution_id}:set-candidate-publication` 仅供 DeploymentAdmin，必须可信 Origin、有效 Session、CSRF、License、`Idempotency-Key`；不可带查询参数。请求为严格 JSON，恰好包含：

```json
{
  "reference_version_id": "当前 GLOBAL ReferenceVersion UUID",
  "expected_event_no": 0,
  "event_kind": "PUBLISH",
  "display_label": "人工审定的非敏感展示标签",
  "reason": "管理员审定原因"
}
```

`event_kind` 仅 `PUBLISH` 或 `REVOKE`。PUBLISH 标签为 NFC、去首尾空白、无控制字符的 1～160 字；REVOKE 标签必须为 `null`。`reason` 为同规则 1～2000 字；`expected_event_no` 为当前 Root 最新事件号（首次 0），同时要求固定 `reference_version_id`。Owner 在同一写事务重证当前 GLOBAL 版本、最新人工 ELIGIBLE 资格、Document/Evidence 物理内容及最新有效人工脱敏确认；撤回允许资格已受限，但仅能撤回同版最新 PUBLISH。原始 Root 名称、来源正文/路径、客户数据、确认声明和管理员会话不得作为项目响应字段。

成功 `200`，`Cache-Control: no-store`，统一 `data`/`trace_id`：`data` 恰含 `publication_event_id`、`reference_solution_id`、`reference_version_id`、`event_no`、`event_kind`、`display_label`、`reason`、`created_at`（UTC `Z`）。同键同正文重放返回原不可变事件，不重写 Audit；不同正文同键冲突。错误沿用 API-01：未授权/不存在统一 404、License 403、CSRF 403、无/过期 Session 401、非法 JSON 400、校验失败 422、版本/状态/同键冲突 409、不可用 503；不向前端回传异常栈或内部来源。

本项仅 `create_app` 可选路由注入，默认 404。Windows 显式生产装配、正式目标账户信任源、项目成员最小候选列表/详情和浏览器验收为后续独立任务；管理员命令响应不得复用为项目读面。关闭路由可回滚 API；已写发布/Audit/收据历史保留，0158 非空拒降。
