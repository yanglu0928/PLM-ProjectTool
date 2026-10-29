# CR-EXEC-022：兼容 A17 上游旧需求来源夹具状态

- 日期：2026-10-29
- 状态：legacy source fixture 修正确认有效，A17 继续到 nested Session 权限问题
- 来源与证据：hosted run 40817646067 的基础 9 个作业、父包 PG lifecycle、A17 候选投影、Caddy HTTPS、Workflow HTTP/Audit、ASCII 输出、Document 固定来源、SectionVersion 创建/校验、Section Review 提交/批准以及 CUSTOMER_MEMBER reviewer fixture 均通过，并输出 `P51_A17_SYNTHETIC_SECTION_OWNER_REVIEW_PASS`。随后 `validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py::_approved_requirement_v2` 在断言旧合成 RequirementVersion 的 `req_sources` 数量为零时失败。该版本由已修正的 P51-A05 fixture 生成，已有恰好一条合法 HUMAN_DECISION source，原验证注释“never seeded its row”已过期；验证随后还计划无条件插入第二行。
- 问题：嵌套验证仍要求旧 fixture 的历史缺口状态，且无条件补录来源行，与当前 A05 合成需求 fixture 不兼容。
- 方案比较：A. 显式读取现有来源数；为历史缺行状态补录一次，对已经有一条的有效状态保持不变，并拒绝大于一条；B. 删除来源完整性检查或允许任意数量。选择 A，保留约束并兼容两种已知合成初态。
- 基线差异：只调整 hosted 验证夹具的兼容准备逻辑；不改产品 Requirement 服务、Schema、业务来源校验、API 或客户数据。
- 影响与风险：仅影响 nested P51/A17 disposable PostgreSQL 数据；如果来源数不是 0 或 1，仍明确失败，避免掩盖夹具污染。
- 回滚：恢复旧零来源断言和历史补录逻辑；不触及正式数据库。
- 验证计划：hosted Windows 2025 复跑；要求来源夹具处理后继续通过 Requirement Review、PlanVersion Edge 与 PG state/cleanup、进程停止和 candidate integrity markers。未达到全链证据不关闭 A27。
- 执行边界：只在 GitHub hosted runner 执行，不在用户本机或 C 盘运行项目代码；不外发客户数据或 Secret。

- 托管复验追加（run 40819285914 attempt 2）：来源数量已兼容并继续到 RequirementVersion 创建；后续 AUTH_ACCESS_DENIED 的 Session 传递由 CR-EXEC-023 追踪。
