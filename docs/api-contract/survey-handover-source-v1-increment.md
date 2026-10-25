# Survey 已批准交接问题来源读取 V1 增量

日期：2026-10-25。依据 `CR-SUR-013`；不改 Gate 2 原冻结 API 合同及原交接/调研写操作。

|Operation|方法及路径|当前 PROJECT 权限|
|---|---|---|
|`SURVEY_HANDOVER_SOURCE_LIST`|GET `/api/v1/projects/{project_id}/survey-handover-sources`|ACTIVE `PROJECT_MANAGER` 或 `IMPLEMENTATION_MEMBER`|

仅当前项目 ACTIVE 交接分析、`current_approved_version_ref` 指向的 APPROVED
版本及 `CONFIRMED/RESOLVED/ACCEPTED_RISK` 问题可见。每项只含
`handover_item_row_id`、`handover_analysis_version_id`、
`handover_analysis_id`、`analysis_item_id`、`project_id`、`title`、`state`。
前四个 ID 为固定来源定位，标题为简短提示；没有原文、文档/Evidence 正文、
路径、AI 内容或内部状态变更。取得候选不授权写入，SurveyVersion 创建时仍在
同一事务重证来源当前性。

列表仅接受唯一 `page_size`（默认 50，1～200）和 `cursor`；稳定按固定行 UUID
升序。`data.items/next_cursor/has_more` 与 `trace_id` Envelope，响应
`Cache-Control: no-store`。签名 cursor 使用独立 `survey-handover-sources`
用途族，绑定会话摘要、项目和页长，复用 Handover item cursor 的现有 Windows
Vault 32 字节密钥；不同用途族不可互用。每次续页重新受权、重新查询当前指针，
不承诺撤源前后的跨页快照一致性；写入口负责最终重证。

匿名/失效会话 401，权限或错项目 404，License 拒绝 403，归档项目 409，
畸形 query/cursor 400，页长 422，内部不可用 503。默认应用不挂载；Windows
显式平台组合挂载。无 Schema/Migration/依赖/License 授权粒度变更。回滚停止
挂载此 GET；原交接 GET、SurveyVersion POST、历史版本和 Audit 不删除。
