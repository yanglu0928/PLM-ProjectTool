# SOL-03-A06-P04-P03-A03-P02：Outline Review 完整来源同库组合

日期：2026-10-24。状态：`PASS`（内部同库组合；无公开送审入口）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A03-P02` |
| 输入基线 | 冻结API-04 Outline提交仅ProjectManager；0185状态闭合；A01现时查询、A02 Subject与A03-P01内部提交 |
| 前置 | A03-P01内部服务/权限通过；A05-P02合成真实Requirement/Section/Trace/Outline三维PG脚本可复用；统一Review核心在Section同库已验 |
| 涉及模块/实体 | Windows内部组合工厂、Outline Review Subject/完整三维来源/统一Review核心；无新实体/Schema |
| 涉及API/权限 | 本片不开放公开HTTP；合成ProjectManager送审、客户确认人资格与Review快照由现有服务把关；终态客户来源以ALL_MEMBERS现时重证 |
| 验收标准 | 同一隔离PG库中正式已批准Requirement/Section与Trace支撑Outline三维PASS；真实Session/License/Project/Reviewer/Review核心/Subject/收据原子START；同Key回放单事实；来源撤销后终态现时重证拒绝；错误项目/版本/角色失败关闭；独立脚本与全量回归 |
| 风险/回滚 | 不能用合成身份冒充客户真实确认；公共VALIDATE仍DRAFT；不修改冻结API；工厂未装配公开入口可撤，已发生的真实Review历史只能前向修复 |

本片只验内部运行组合和一次性Win11/PG，HTTP及浏览器属于后续分片。

## 实施与独立验收

- 将现有 Outline VALIDATE 的完整来源图抽成单一 Windows 内部工厂，保留公开 VALIDATE 的 DRAFT 边界；Review START 消费同一版本的顺序、固定来源、批准需求全集/章节 Trace 覆盖，批准前终态重证配置章节证据按 `ALL_MEMBERS` 读取。新增内部 Subject/提交组合工厂，但不挂载公开路由。
- `validation/sol-03-a06-p04-p03-a03-p02-outline-review-pg-composition/verify.py` 在 Win11 一次性 PG18.6 中重用正式合成 Requirement/Section/Trace/Review 来源：Outline DRAFT 三维均 PASS；真实 Session/License/ProjectManager 与合格合成客户成员走统一 Review 核心，单 Review/Round/快照/START/收据落库；同 Key 回放只返回首次结果；错项目、错版本和异 Key 重复送审均拒绝。撤销当前 Trace 后 `IN_REVIEW` 终态现时重证拒绝，版本维持 IN_REVIEW、结果仍仅 START；脚本 exit 0，临时数据库清理。
- 原计划在“已送审同根版本”之后再验证“新提交被撤源拒绝”，但 0185 Guard 禁止评审中创建后续版本，而不同根不能复用原章节，故改为同版本批准前终态重证拒绝。此为验证路径调整，不更改冻结合同；A01 既有 DRAFT 撤源 coverage 非 PASS 证据保留。未用测试绕过 Guard。
- 后端全量 `4052 passed, 3 skipped, 6112 subtests passed`；原 Outline VALIDATE Windows 组合定向 11 项/65 子例亦通过。

## 边界与后续

合成客户成员、合成 License/信任不等于真实客户签署或正式安装。内部服务仍未挂到公开 HTTP，也未接入统一 Review 的运行时读取/终态分发器；后续拆片接入冻结 `:submit-review`、Review 读/终态、Windows 显式装配和浏览器验收。无 Schema/冻结 API/角色权益迁移；停止装配即可撤内部工厂，真实历史不可删除。Pilot/Gate3/正式发行未通过。
