# SOL-03-A06-P04-P03-A02：Outline 统一 Review Subject

日期：2026-10-24。状态：`PASS`（内部 Subject/仓储和隔离 PG 事务；未装配公开送审）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A02` |
| 输入基线 | 冻结DM-05/API-04、统一Review Subject固定送审合同；0185状态闭合；A01内部IN_REVIEW现时三维重证 |
| 前置 | Gate2已通过；Outline DRAFT完整三维真实PG、Section统一Review参考实现及数据库状态窄门已验。没有直接开放Outline送审入口 |
| 涉及模块/实体 | solution/review/application与solution仓储；Outline根、固定Version、Review/Round/SubjectSnapshot、客户确认人 |
| 涉及API/权限 | 无新公开API；内部Subject为`SOL-03`/`SOLUTION_OUTLINE_ALL_V1`，送审者仅由上层项目授权决定，确认人必须合格客户成员 |
| 验收标准 | 最新同根Version锁定；DRAFT三维当前PASS才准备送审；Review/Round/版本/摘要/确认人固定；终态批准前IN_REVIEW重新证明；状态、指针和结果与0185同事务闭合；错项目、错版本、漂移/撤权、回放拒绝/允许边界与原子回滚实测 |
| 风险/回滚 | 不能复用Section主体类型或旧VALIDATE Audit；不能伪造客户确认。内部服务未装配可撤，已形成真实评审历史不可删除，需前向修复 |

本片只建Subject/仓储，不开放HTTP/Windows正式组合。客户决定仍只能由后续实际身份/统一Review完成。

## 实施与独立验收

- 新增 `SOL-03`/`SOLUTION_OUTLINE_ALL_V1` Outline Subject Owner、最新版本共享/独占锁与当前三维重证。只有 `DRAFT` 最新版本能准备/固定送审；批准前 `IN_REVIEW` 同事务重证，并重新核对项目、版本、Review/Round、内容指纹和客户确认人资格。旧 VALIDATE 审计不能替代当前证明。返回/撤回不伪造批准。
- 仓储在同事务绑定 START 结果、IN_REVIEW 版本状态；终态同时写版本、批准指针和不可变结果，失败即回滚。数据库 0185 Guard 独立核对 Review/Round/快照/结果，不接受状态或指针孤立更新。无新 Schema、公开 API、角色或 License 变更。
- 定向单元 29 项通过：三维 PASS/FAIL/UNAVAILABLE、最新版本和状态、错误身份/指纹/轮次、确认人撤权、审批前重新证明、共享锁 SQL；后端单元全量 `3454 passed, 3 skipped, 4793 subtests passed`；后端全量 `4045 passed, 3 skipped, 6107 subtests passed`。
- Win11/一次性 PG18.6 合成事务脚本 `validation/sol-03-a06-p04-p03-a02-outline-review-subject/verify.py` 退出 0：错误项目拒绝；故意中断 START 后 DRAFT/零结果；正常 START 单条结果；合成统一 Review 终态后 APPROVED/根指针/两条不可变结果同事务闭合。脚本只使用合成身份，终态核心历史夹具由测试直接设置，不代表真实客户决定或端到端 Review HTTP。

## 边界与后续

本片未挂载到运行时 Review 分发器，不开放 `:submit-review`/浏览器，也未测试正式公钥/服务账户、真实客户确认或发行。下一片 `SOL-03-A06-P04-P03-A03` 做真实统一 Review 原子送审装配与同库完整现时事实验证，再分片做 HTTP/Windows/浏览器。内部服务可撤；已经生成的真实评审历史不得删除，须前向修复。Gate 3、Pilot 与正式 Release 不因此通过。
