# SectionVersion VALIDATE V1 实施细化（未开放）

日期：2026-10-12；WBS `SOL-05-A04-P02`；依据 Gate 2 冻结 API-04 的 `SOL_SECTION_VERSION_VALIDATE` 与 DEC-1188。本文件细化尚未实现的 200 报告形状，不改变冻结路径、方法、角色或现有已发布响应；HTTP Router 与真实 Owner 未装配，不得将示意响应当生产可用。

`POST /api/v1/projects/{project_id}/solution-sections/{section_id}/versions/{section_version_id}:validate` 仅项目 ProjectManager/ImplementationMember，当前 Session Cookie、CSRF、License、项目授权、Idempotency-Key 必须在 Owner 同事务核对。请求无 JSON 正文；请求指纹仅绑定 Project/Section/固定 Version。成功调用的 200 表示“本次验证报告已审计”，不表示报告 `valid=true`、允许 Review 或客户批准。错误使用既有 `{error:{code,message},trace_id}`，不得返回未审计的猜测结果。

报告 `data` 的最小字段：`audit_event_id`、`project_id`、`solution_section_id`、`solution_section_version_id`、`version_no`、`version_state`、`content_fingerprint`（hex）、`requirement_count`、`evidence_count`、`facts`、`valid`、`ready_for_review`、`issue_codes`、`observed_at`。外层沿用 `{data,trace_id}`。`facts` 必须完整含 `integrity`、`content`、`requirements`、`evidence`、`trace`、`spec` 六项，每项仅 `PASS/FAIL/UNAVAILABLE`；未知、无适配器、异常或证明缺失不得省略或默认为 PASS。`issue_codes` 依此顺序由未 PASS 项派生，非 DRAFT 额外以 `VERSION_NOT_DRAFT` 开头。固定身份、时间、审计 ID、问题码和布尔结论不一致时服务端失败关闭。

`valid` 仅当固定完整性、正文、需求与证据四项均 PASS；`ready_for_review` 还要求 Trace/Spec 均 PASS 且版本仍为 DRAFT。报告绝不直接修改不可变 SectionVersion，也不创建 Review、改变当前批准指针或代替客户签署。现阶段 StructuredSpec/Trace 的真实章节验证 Owner 缺失，不能产生可信的 `PASS`；当前合同单元测试中的全 PASS 仅用于校验布尔规则。

首次请求须将 `V1_SOL_SECTION_VERSION_VALIDATE` 收据和 `SOL_SECTION_VERSION_VALIDATED` 审计与报告事实同事务提交，Audit `reason_code` 采用固定六位 `SECTION_VALIDATION_V1_[PFU]{6}`，每位与上述维度顺序一致；Audit `SUCCESS` 指命令执行成功，不代表业务报告通过。相同操作者/项目/操作/Key 只可返回首次审计的报告、Trace 和观察时间，不重新采样当前来源；新 Key 才产生新的现时观察。回放须先再次通过 Session、License 与项目授权，且核对收据指向原版本及 Audit 归属。真实同事务 Owner、故障回滚、HTTP 投影与 Windows 装配留后续 WBS 验收。
