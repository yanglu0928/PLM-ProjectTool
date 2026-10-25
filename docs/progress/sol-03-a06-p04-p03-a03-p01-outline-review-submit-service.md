# SOL-03-A06-P04-P03-A03-P01：Outline Review 内部原子提交服务

日期：2026-10-24。状态：`INTERNAL_SERVICE_PASS / PG_COMPOSITION_PENDING`。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A03-P01` |
| 输入基线 | 冻结API-04 `SOL_OUTLINE_VERSION_SUBMIT_REVIEW`（ProjectManager、201 Review/Round）；0185状态闭合；A02 Outline Subject；统一Review提交合同 |
| 前置 | Gate2已通过；A02 Subject/仓储隔离PG原子状态闭合已验，Section提交服务可参考；无正式公开Outline提交入口 |
| 涉及模块/实体 | solution应用提交服务、project权限矩阵；复用Review/Round/快照、OutlineVersion、收据/Audit，不改Schema |
| 涉及API/权限 | 不增加公开API；内部操作`SOL_OUTLINE_VERSION_SUBMIT_REVIEW`仅PROJECT_MANAGER；1～32位当前合格客户确认人 |
| 验收标准 | 会话/CSRF/License/项目负责人授权；同事务锁客户与Outline最新DRAFT，现时三维PASS并固定快照；Review/Round/START/幂等收据/Audit原子提交；同Key仅回放原历史，跨项目/错版本/撤权失败关闭；定向与全量回归 |
| 风险/回滚 | 不把旧VALIDATE或测试身份当真实批准；不复用SOL-05策略；服务未装配可撤，真实评审历史不可删除须前向修复 |

本片只做内部服务和权限映射；现时完整来源的Windows装配、HTTP/浏览器、正式客户确认分片验收。

## 实施与验收

- 新增 `SubmitOutlineReview`/`OutlineReviewSubmissionService`，固定 Project/Outline/Version/客户确认人/策略身份；真实会话、CSRF、License、仅 ProjectManager 写入权限、受控确认人锁、统一 Review 持久化和 A02 Subject 在同一 Unit of Work 内执行。Review/Round/固定快照/START/收据/Audit 由现有统一 Review 核心及 Subject 组合负责；本片不接受客户端指纹或旧 VALIDATE 报告作为送审事实。
- 同 Key 只读取第一次 Review/Round/收据并复核主体访问；错项目、错角色、错误版本/策略/确认人、License 失效及证明失败关闭；仅对被识别的 PostgreSQL 死锁有界重试。操作权限 `SOL_OUTLINE_VERSION_SUBMIT_REVIEW` 仅 `PROJECT_MANAGER`。
- 定向服务/权限 17 项与 841 子例通过；后端全量 `4052 passed, 3 skipped, 6112 subtests passed`。A02 已有隔离 PG Subject START 故意回滚与状态结果闭合证据，但本片尚未用真实 Outline 来源/Review 核心在同库执行服务，因此只标内部服务已验，不冒称端到端原子送审。

## 边界与后续

下一片 `SOL-03-A06-P04-P03-A03-P02` 装配当前完整三维来源与统一 Review 核心，在 Win11 隔离 PG 验证真实事务、幂等回放和拒绝路径；之后再做 HTTP/Windows 显式入口及浏览器。无新 Schema/公开 API/License 权益；撤内部未装配服务和操作映射即可回滚，已有真实评审历史只允许前向修复。Pilot/Gate3/正式发行不变。
