# SectionVersion VALIDATE V1 实施细化（未开放）

日期：2026-10-12；WBS `SOL-05-A04-P02/P04/P06`；依据 Gate 2 冻结 API-04 的 `SOL_SECTION_VERSION_VALIDATE` 与 DEC-1188/1190/1191。本文件细化 200 报告形状，不改变冻结路径、方法、角色或现有已发布响应；真实内部 Owner、可选 Router、Windows 11 显式写链已按 P03～P05 验证，默认仍未装配；真实浏览器与正式信任尚未验收。

`POST /api/v1/projects/{project_id}/solution-sections/{section_id}/versions/{section_version_id}:validate` 仅项目 ProjectManager/ImplementationMember，当前 Session Cookie、CSRF、License、项目授权、Idempotency-Key 必须在 Owner 同事务核对。请求无 JSON 正文；请求指纹仅绑定 Project/Section/固定 Version。成功调用的 200 表示“本次验证报告已审计”，不表示报告 `valid=true`、允许 Review 或客户批准。错误使用既有 `{error:{code,message},trace_id}`，不得返回未审计的猜测结果。

报告 `data` 的最小字段：`audit_event_id`、`observation_trace_id`、`project_id`、`solution_section_id`、`solution_section_version_id`、`version_no`、`version_state`、`content_fingerprint`（hex）、`requirement_count`、`evidence_count`、`facts`、`valid`、`ready_for_review`、`issue_codes`、`observed_at`。外层沿用 `{data,trace_id}`；外层 `trace_id` 与 `X-Trace-Id` 为本次 HTTP 请求，`observation_trace_id` 为首次审计 Trace，同 Key 重放时保留原值。`facts` 必须完整含 `integrity`、`content`、`requirements`、`evidence`、`trace`、`spec` 六项，每项仅 `PASS/FAIL/UNAVAILABLE`；未知、无适配器、异常或证明缺失不得省略或默认为 PASS。`issue_codes` 依此顺序由未 PASS 项派生，非 DRAFT 额外以 `VERSION_NOT_DRAFT` 开头。固定身份、时间、审计 ID、问题码和布尔结论不一致时服务端失败关闭。

`valid` 仅当固定完整性、正文、需求与证据四项均 PASS；`ready_for_review` 还要求 Trace/Spec 均 PASS 且版本仍为 DRAFT。报告绝不直接修改不可变 SectionVersion，也不创建 Review、改变当前批准指针或代替客户签署。现阶段 StructuredSpec/Trace 的真实章节验证 Owner 缺失，不能产生可信的 `PASS`；当前合同单元测试中的全 PASS 仅用于校验布尔规则。

首次请求须将 `V1_SOL_SECTION_VERSION_VALIDATE` 收据和 `SOL_SECTION_VERSION_VALIDATED` 审计与报告事实同事务提交，Audit `reason_code` 采用固定六位 `SECTION_VALIDATION_V1_[PFU]{6}`，每位与上述维度顺序一致；Audit `SUCCESS` 指命令执行成功，不代表业务报告通过。相同操作者/项目/操作/Key 只可返回首次审计的报告、观察 Trace 和时间，不重新采样当前来源；新 Key 才产生新的现时观察。回放须先再次通过 Session、License 与项目授权，且核对收据指向原版本及 Audit 归属。P03 真实同事务 Owner/故障回滚、P04 HTTP 投影合同、P05 Windows 11 ASGI/PG 链已验；P06 前端仅提交零正文受控请求并严格检查报告，断线/503 保留原 Key、不自动换号。页面与真实 Edge 浏览器留后续 WBS 验收。

2026-10-23 增量说明（CR-SOL-023 / `SOL-05-A04-P12-P05-P02`）：前述“Trace/Spec Owner 缺失”属于原实施时状态，Trace 当前证明已另片接入；本片新增可选Spec现时证明合同，不改变本页路径、角色、状态枚举或报告形状。`spec=PASS`只表示DRAFT的显式`NONE_REQUIRED`有规范理由且零固定引用，或`FIXED_REFS`逐条有作者适配依据并通过同事务现时批准Spec/Review/章节祖先/共同需求证明；不是语义自动正确或客户批准。缺真实Spec适配器、无依据、证明不完整或异常仍为`UNAVAILABLE`。Windows/PG实际接线留P05-P03验收，不能以本合同单元测试宣称已开放。

2026-10-23 `SOL-05-A04-P12-P05-P03`：Windows显式VALIDATE组合已接入上述现时Spec只读证明，并在一次性PG18库完成有依据PASS、旧缺依据UNAVAILABLE、当前批准失效后新Key UNAVAILABLE/旧Key首次结果回放。此处PASS仍仅为送审准备；实际Trace+Spec同时PASS、Section正式Review、客户确认和Pilot/Gate验收尚待。
