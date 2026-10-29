# CR-EXEC-020：使 A17 Section Review 提交夹具符合 HTTP 合同

- 日期：2026-10-29
- 状态：已记录，待实施与托管验收
- 来源与证据：hosted run 40813762335 中，A17 已通过父包/候选构建、PostgreSQL 生命周期、Caddy HTTPS、Workflow GET/START/replay/CSRF/conflict/Audit、ASCII 控制台输出及 SectionVersion Document 固定来源证明。随后合成 Section Review 提交返回 `VALIDATION_FAILED`。核对 `apps/backend/src/plm_assistant/modules/solution/api/section_submit_review.py` 确认 API 接受的字段值必须为 `reviewer_ids` 列表、`policy_ref=SOLUTION_SECTION_ALL_V1`、`due_at=null`、`submission_note=null`；A17 夹具发送了非空 `submission_note` 字符串。
- 问题：验证夹具请求违反当前已实现 HTTP 合同，无法继续执行 Section Review / PlanVersion 浏览器链。
- 方案比较：A. 把合成请求的 `submission_note` 改为合同要求的 null；B. 放宽 HTTP/API 校验接受自由备注。选择 A，仅修夹具请求，不扩大产品合同或未经基线批准的请求字段语义。
- 基线差异：仅修正 A17 合成验证请求值；不改 API、应用服务、数据模型或业务策略。
- 影响与风险：仅影响 A17 synthetic review 数据；符合冻结的 API 行为。回滚为恢复错误的字符串输入。
- 验证计划：GitHub hosted Windows 2025 执行相关验证与 A17 全链，要求 Section Review 创建/批准通过，继续到 PlanVersion Edge/PG 状态及清理/候选完整性 markers。未达全链 markers 不关闭 A27。
- 执行边界：只用 GitHub hosted runner；不在用户本机或 C 盘执行项目代码，不外发客户数据或 Secret。
