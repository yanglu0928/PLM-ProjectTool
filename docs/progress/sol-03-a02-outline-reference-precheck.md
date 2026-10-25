# SOL-03-A02：OutlineVersion 固定来源与参考关联前置复核

日期：2026-10-09。结果：`SOL_03_A02_REFERENCE_LINK_PRECHECK_COMPLETE`；只完成静态前置与 CR 计划，版本写仍 `PRECONDITION_BLOCKED`。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A02。输入：Gate2 冻结 DM-05/API-04、CR-SOL-002、0137～0153、SOL-04-A21、REQ-01 Review/批准证明、SOL-01-A16-P06-P03；原 A01 的 Section/Reference 缺口已部分关闭。
- 单一问题：确定 OutlineVersion CREATE 所需固定来源结构、最小安全迁移与 Owner 解锁次序，不在本项创建正式版本。
- 模块/实体/API/权限：Solution/Requirement/Project/Review；OutlineVersion、Section 身份、RequirementVersion、ReferenceVersion；冻结 CREATE/GET/VALIDATE/Review，CREATE 仍 PM/实施成员。验收为核实当前 Schema/Owner 与冻结输入一致性、明确下一任务及失败关闭/回滚；风险是把合成资格或历史读当现时合格。

## 核查证据

1. 0137/ORM 已固定有序 Section 身份和同 Project RequirementVersion，且 OutlineVersion/两关联表仍由 `guard_solution_outline_version_foundation()` 拒全部 DML；`sol_outline_reference_refs` 未定义。CR-SOL-002 已明确不得使用无 FK 的参考 UUID。
2. SOL-04 Section 身份 CREATE/GET/LIST 与 Edge/PG 合成链已通过；REQ-01 有当前 APPROVED RequirementVersion 的 Repository 证明端口；SOL-01-A16 有 PROJECT/GLOBAL 人工资格、当前来源重证、修订旧合格失效及 Edge/PG 合成链。以上使固定参考 Schema 能设计，但并不产生 Approved SectionVersion 或 OutlineVersion。
3. ReferenceVersion 自身状态仍是 DRAFT；人工资格在 Root 且绑定其当前版本。OutlineVersion Owner 必须检查请求所指 Version 等于 Root 当前版本、Root 为 ELIGIBLE、PROJECT 同项目或 GLOBAL 确认现时有效，以及底层 Document/Evidence 真实可用。历史 ELIGIBLE 事件或固定 FK 都不能替代重证。
4. 冻结 API-04 定义 CREATE 为 201 DRAFT、GET 返回固定 order/requirement/reference refs，VALIDATE 和 SUBMIT_REVIEW 分离；不得从初态 CREATE 自动批准或把 AI 建议正式化。

## 施工顺序与边界

下一项 `SOL-03-A03` 只建封闭参考版本关联 Schema/ORM/线性 Alembic 迁移，旧 0137 Guard 保持，按 CR-SOL-002/DEC-1138 做空/有数据 up/down、Drift 与 SQL 负例。再独立做受权 CREATE Owner/Guard 原子解锁、HTTP、Windows、前端/浏览器，以及 VALIDATE/Review/Trace/Workflow。Owner 前的正式版本创建继续阻塞。SectionVersion 的批准正文仍是最终正式方案输出条件，不因目录 DRAFT 而豁免。

本项无程序、Schema/Migration、API、依赖、Secret、客户数据外发；只做冻结合同、ORM、Migration 与既有证据静态核对，未运行新测试。可撤实施排序，不能撤历史与 Gate 阻塞。TraceLink：Gate2 DM-05/API-04 → CR-SOL-002 → SOL-03-A01 → SOL-04-A21/REQ-01/SOL-01-A16 → 本 A02/DEC-1138 → A03 → Gate3。
