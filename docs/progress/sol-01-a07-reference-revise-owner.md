# SOL-01-A07：Reference 修订内部受权 Owner

日期：2026-10-09。结果：`SOL_01_A07_REFERENCE_REVISE_OWNER_PG_PASS`；仅内部应用服务/仓储/Guard，`SOL_REFERENCE_REVISE` 公开 HTTP、Windows 注入和前端仍未开放。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A07；Gate 2 冻结 API-04/DM-05、CR-SOL-013 与 A05/A06 前置满足。
- 模块/实体/API/权限：Solution Reference 根、不可变版本/有序来源、首次结果；Project 授权新增冻结操作 `SOL_REFERENCE_REVISE`（PM/实施成员），GLOBAL 沿用 DeploymentAdmin；无 `/api/v1` 路径/响应公开变更。
- 输入：0149 闭锁结果表、原 Reference Create/Source Qualification、Auth Session/CSRF、Runtime License、Receipt/Audit。数据库版本 `20261009_0150` 只变更 Guard/约束触发器，ORM 表形状不变。
- 验收：新版本线性 supersedes，根仅指针和 lock_version 推进，来源/结果原子闭合；首次 201 历史重放；同/异 Key 并发、跨项目/角色/CSRF、GLOBAL 脱敏绑定、Audit 失败回滚、直接 SQL 非法 DML、空库/有 v1 升降重升、legacy v2 拒升级、历史拒降、drift、全量回归。
- 风险：0149 之前可能已有无首次结果的 v2；不能凭当前指针伪造原 201，0150 升级前显式拒绝，需审计后向前修复。数据库触发器是数据完整性边界，不替代应用授权或目标账户最小权限。

## 实施与证据

新增 0150：修订版本只能指向同根前一序号；根仅允许指针/锁版本加一且必须指向相邻新版本；首次结果只可插入与版本/当前指针精确匹配的行，禁止后续改删；延迟约束在提交时要求版本、根当前指针、不可变结果与所声明来源数量闭合。原 v1 创建 INSERT 继续有效。存在历史 v2 或结果时降级拒绝，避免丢失受控修订语义；历史 v2 无原结果时升级拒绝，不自动回填。

内部 `ReferenceReviseService` 先核验 Session/CSRF、License，再在同事务重新核验权限、锁根、重新证明 Document/Evidence/GLOBAL 脱敏确认，插入新版本/有序来源、推进当前指针、存首次结果、Audit 与 Receipt。重放在重新授权后从不可变结果读原新版本，允许之后已有更高版本；Eligibility 保持原状态且不据此宣称来源现在仍合格。公开路由不装载。

Win11 一次性 PG18.6：PROJECT 实际合成 Auth/Document/Evidence/私有文件下 PM/IM 修订、同 Key 两线程重放、不同 Key 竞态仅一个成功、跨项目/客户角色/CSRF 拒绝、第三版后第二版重放、Audit 故障原子回滚、非法根/版本/结果 UPDATE/DELETE/TRUNCATE 与缺闭合版本提交拒绝通过。GLOBAL 已确认来源修订、改变来源但沿用旧脱敏确认拒绝通过。迁移空库/有 v1 升降重升、四次 drift、legacy v2 拒升级；有修订历史拒降。后端全量 `3370 tests OK, skipped=3`。

## 兼容、升级与后续

0149→0150 线性升级；生产升级前检查历史 v2/result，若有则保持 0149 并做逐条审计/迁移方案，不删除或伪造历史。空/仅 v1 可降回 0149；有修订历史不降，向前修复。无依赖/前端/冻结 API 变更。TraceLink：Gate2 API-04/DM-05 → CR-SOL-013 → 0149/A06 → 0150/A07 → A08 HTTP/Windows → UI/Eligibility。正式目标账户、公钥/Vault/HTTPS、20 并发、Server2025、Gate3/UAT/可用程序包仍未验；Debian13 实机按用户指令暂跳过。
