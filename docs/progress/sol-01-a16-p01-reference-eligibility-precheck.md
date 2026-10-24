# SOL-01-A16-P01：Reference Eligibility 前置核查

日期：2026-10-09。结论：`SOL_01_A16_P01_PRECHECK_PASS`；仅状态机/偏差/迁移边界设计完成，资格功能尚未实现、未验收。

## 编码前检查与单一问题

Phase 2 / SOL-01-A16-P01；对照冻结 API-04、DM-05、CR-SOL-014、0139 根、0144 INSERT-only、0150 修订 Guard、0151 修订真实锁快照、Evidence 首次决定 Owner。当前分支 `feature/license-runtime-guard`，用户既有 `.tmp/` 不纳入。前置满足：冻结资格路由/角色可追溯、现有 Reference Create/Revise 双 Scope 已有 Win11 隔离 PG/Edge 合成证据；但正式资格 Owner/HTTP/UI 尚无。单一问题是定义资格状态机、当前版本绑定、受限写与可回滚迁移，不改生产代码。

## 核查发现

- 冻结 `SOL_REFERENCE_SET_ELIGIBILITY` 是 PROJECT ProjectManager/GLOBAL DeploymentAdmin 独立人工命令，S/L/C/I/M/A，返回 200 eligibility/reason；不把 Reference 自动变成项目事实。
- 根已有四状态、原因、锁版本，0144 只准 INSERT；0150 只准修订指针+锁，0151 的不可变修订结果存真实锁版本。因此直接根 UPDATE 会被 Guard 拒绝，扩大通用 UPDATE 会破坏冻结历史。
- Evidence 首次资格只处理 CANDIDATE；Reference 有 RESTRICTED 可恢复与 REVOKED 终态，不能照搬 Evidence 状态机/同号响应规则。
- 修订当前保留旧 `ELIGIBLE`，新版本可能获得旧资格表象。此偏差已在 CR-SOL-014 记录保守失效规则，覆盖 A14 的“修订不自动改变资格”规划；旧资格事件/旧 200 不证明新版本合格。

## 后续分片与验收门槛

1. A16-P02：仅 Schema/ORM/Guard/不可变事件与结果快照，写一次线性 Alembic；空库及已有版本升级、空历史降重升、非法遗留 ELIGIBLE 拒升、存在资格历史拒降，直接 SQL 越权 DML 负例，drift。
2. A16-P03：内部人工命令 Owner，当前版本固定来源与实时 Document/Evidence、GLOBAL 人工脱敏确认同事务复验；状态机、授权/隔离、强 If-Match/同号快照、Audit/Receipt 原子性及并发。修订失效规则与新 Guard 一起验证，不能先打开可写面。
3. A16-P04～P06：默认关闭 HTTP 合同、Windows 显式组合/隔离 PG、受权前端及 Win11 Edge 合成整链。每步只证明自身；合成勾选不等于用户本人确认。

回滚优先停用可选入口并保留历史；有资格事件的 DB 不回退至不理解它的旧版。正式 License/目标账户/Server2025、20 并发、Gate3/UAT/程序包仍待，Debian13 实机依用户要求跳过。TraceLink：Gate2 API-04/DM-05 → CR-SOL-014 → 本 P01 → P02～P06 → Gate3。
