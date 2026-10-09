# SOL-01-A16-P02：Reference Eligibility 闭合事件 Schema

日期：2026-10-09。结果：`SOL_01_A16_P02_REFERENCE_ELIGIBILITY_SCHEMA_PASS`，仅不可变结果/事件存储底座通过；资格 Owner/根 Guard/HTTP 尚未开放。

## 编码前检查

- Phase/WBS：Phase 2 / SOL-01-A16-P02；输入冻结 API-04/DM-05、CR-SOL-014（A16-P01 已先记录修订失效）、0139/0144/0150/0151 与 P01 状态机，前置满足。
- 单一问题：建立可记录人工资格决定与系统版本失效的事件/首次 200 结果快照，保持默认拒绝写入。无公开 API、角色、外部依赖或前端变化。
- 基线：`20261009_0151` → `20261009_0152` 单线迁移；原 Gate2 `64cdf09` 不改。

## 实施

- 新增 `sol_reference_eligibility_events` ORM/表，事件含根/固定版本/Scope/Project、种类、前后状态、原因、操作者、前后锁版本与时间；一条事件同时是同号首次结果快照，后续 Owner 以事件 ID 作为幂等 Receipt 引用。CHECK 限四状态允许转换、固定系统失效原因、非空规范化原因、连续锁版本；FK 绑定版本/操作者/项目，根+结果锁版本唯一。
- 迁移在建表前拒绝已有非 `REFERENCE_ONLY` 或有原因却无可信事件的历史根，不回填伪人工决定。新表 INSERT/UPDATE/DELETE、TRUNCATE 均闭合；现有根修订 Guard 不改，直接资格 UPDATE 仍拒绝。
- 空历史可降级；有事件拒降。回滚优先停止未来可选入口，已存事件不删，采用前向修复。正式 A16-P03 必须让受限根 Guard、事件插入、同事务 Audit/Receipt 与修订旧资格失效一并验证后才可开放写入。

## 验证与边界

- Win11 一次性隔离 PostgreSQL 18.6：空/已有首版根 `0151→0152`、空历史降级/重升、Alembic drift 4 次无新增操作；关闭写入、状态/原因/FK/唯一约束、直接根 UPDATE/TRUNCATE 负例；仅验证 Schema 时临时停事件 INSERT/DELETE 触发器，确认有事件拒降后清理测试数据；不将绕过动作带到程序运行。
- 故意构造无可信事件的历史 ELIGIBLE 根，升级被拒，未猜测当前资格。首轮脚本期望错误文本不符而失败，修正为实际现有 0150 Guard 报错后完整重跑通过。
- 后端全量 3398 passed、3 skipped、5154 subtests passed；迁移合同与 ORM 注册断言已随新 Head 更新。
- 未验证资格 Owner/真实来源/人工角色/HTTP/Windows 组合/浏览器；真实 License/正式目标账户、Server2025、20 并发、Gate3/UAT/发行仍待。Debian13 实机依用户要求跳过。

TraceLink：Gate2 API-04/DM-05 → CR-SOL-014 → A16-P01 → 本 P02 → A16-P03～P06 → Gate3。
