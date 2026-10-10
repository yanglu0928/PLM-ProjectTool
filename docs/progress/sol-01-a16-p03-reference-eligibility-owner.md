# SOL-01-A16-P03：Reference Eligibility 内部 Owner 与受限 Guard

日期：2026-10-09。结果：`SOL_01_A16_P03_REFERENCE_ELIGIBILITY_OWNER_PG_PASS`，仅内部命令及 PG 组合验证；公开 HTTP、Windows 正式组合和用户界面未开放。

## 编码前检查

|项目|内容|
|---|---|
|当前 Phase/WBS|Phase 2 / SOL-01-A16-P03|
|输入基线|Gate2 API-04/DM-05、CR-SOL-014、0152 闭合事件表；原冻结 `64cdf09` 保留|
|前置任务|A16-P01 状态机/偏差先记录，P02 `0152` 迁移/ORM/默认拒写验收通过|
|涉及模块/实体|Solution Application/Domain/Repository；Reference 根/当前版本/不可变资格事件、Audit/Receipt、Project 授权|
|涉及 API|不挂载公开 API；后续仍用冻结 `SOL_REFERENCE_SET_ELIGIBILITY`|
|权限|PROJECT ProjectManager；GLOBAL DeploymentAdmin；真实 Session/CSRF/License；跨项目隐藏|
|验收标准|状态机与强锁/同号首次结果、实时来源/GLOBAL 确认、事件/根/Audit/Receipt 同事务、修订旧 ELIGIBLE 失效、SQL 越权 DML、空/有 v1 库迁移与回滚|
|风险|0152 初次人工决定被错误锁下界挡住；新 Guard 与修订首次结果闭合可能冲突；真人确认和生产信任源未验|

## 变更

- CR-SOL-014 增记 `0152` 的正常首版根锁 `0` 与事件约束 `>=1` 不兼容；不改已发布 0152，由 `0153` 前向修复为 `>=0`，结果锁仍为前锁 +1。`0153` 还开放**仅事件支撑的**根资格状态更新、固定版本修订导致旧 ELIGIBLE 保守降为 RESTRICTED；事件插入前校验原根/版本，延迟约束校验事务最终根与事件闭合。无事件/状态历史才允许降至 0152，其他历史保留并前向修复。
- 增加纯状态机和内部资格服务：受权操作者、许可与强锁、1～2000 字符规范原因；ELIGIBLE 时同事务重建当前版本固定来源，并调用既有 Document/Evidence 真实证明与 GLOBAL 当前人工脱敏确认，要求来源指纹及固定确认 ID 一致。历史同号 200 从不可变事件返回，不误作当前资格。
- Repository 行锁读当前根/版本/有序来源；先插资格事件、再受限更新根，最后同事务写 Audit 与幂等 Receipt。PROJECT 授权矩阵新增 Manager-only 操作。修订 ELIGIBLE 根时自动插入 `SYSTEM_INVALIDATION` 事件、固定原因和独立 Audit；其他状态保留，REVOKED 不复活。
- 没有新增 HTTP、前端入口、厂商 SDK、依赖或跨模块业务事实；AI 建议不能直接成为人工作决定。

## 验证

- Win11 临时 PG18.6：`0152→0153` 空/已有 v1 根升级、空历史降重升、drift 无新增操作；`v0→v1` 首决策，根无事件直接 UPDATE、事件单独提交、错误原状态、事件 UPDATE/DELETE/TRUNCATE、存在历史拒降均验证。
- PROJECT 真实 Session/私有文件/Document/Evidence：Manager 与同 Key 并发/历史响应；成员、跨项目、错误 CSRF、License 拒绝；审计失败整事务回滚；RESTRICTED→重新 ELIGIBLE、修订旧资格失效、来源篡改拒重新升格、REVOKED 终态。
- GLOBAL 真实 Session/固定来源/人工脱敏确认：当前指纹与确认 ID 绑定；文件篡改、确认撤回均拒重新 ELIGIBLE；确认恢复仅在隔离测试库中以测试触发器旁路还原上游夹具，然后重新资格；GLOBAL 修订旧资格也自动失效并同号返回原修订结果。合成脚本勾选不代替用户本人确认。
- 既有 PROJECT/GLOBAL Reference 修订隔离 PG 回归退出 0；后端全量 `3401 passed, 3 skipped, 5179 subtests passed`。历史 `0152` 验证脚本调整为只在当前 `0153` Head 做 drift，仍测试 0152 闭合状态且退出 0。

## 遗留边界

公开 HTTP/Windows 显式组合/UI/Edge 在 A16-P04～P06；正式 License/目标账户/HTTPS、Server2025、20 并发、Gate3/UAT/发行未验。Debian13 实机依用户指令暂跳过。资格结果是历史人工事件，引用方仍须核验当前版本与实时来源；不得仅凭根 ELIGIBLE 或首次 200 建立正式项目事实。

TraceLink：Gate2 API-04/DM-05 → CR-SOL-014 → A16-P01/P02 → 本 P03 → A16-P04～P06 → Gate3。
