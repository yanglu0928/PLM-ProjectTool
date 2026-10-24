# SOL-05-A04-P11-P04-P02-A02：固定 SpecRef 同事务写入前置检查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_INTERNAL_PASS`；固定 SpecRef 写入已开放，但不等于章节验证/客户确认。

|检查项|结论|
|---|---|
|Phase/WBS|Phase 2 / `SOL-05-A04-P11-P04-P02-A02`；单一问题是把已经验收的固定 Spec 候选资格用于 SectionVersion CREATE 的原子不可变集合|
|输入基线|Gate 2 冻结 DM-05/API-04、CR-SOL-022、DEC-1203/1204、0178/0179、P02-A01 Win11/PG 资格证明|
|前置|可选 FIXED_REFS 输入与反读已存在，但入口 503；Section 当前 Base、真实来源证明、SOL-06 当前批准 Review 快照均存在|
|模块/实体|Solution SectionVersion 根/SpecRef 子表、输入资格与内容指纹、首次结果/幂等收据/Audit；Review 只使用公共快照 Port|
|API/权限|复用原 `/api/v1` CREATE、PM/实施成员、Session/CSRF/License；无新路由、角色、功能权益或客户自动确认|
|验收|同事务现时重证资格、固定集合指纹、根/子表数量与连续顺序/封印、同 Key 回放、失败零写、旧请求/首响不变；Win11 空/旧库迁移升降、真实 HTTP/PG 与完整后端回归|
|风险|若只改应用 503 而不开放且封闭子表，根/子行可能错配；若先开放 Guard 不封印，会允许历史补写；若只核历史批准，会写入已替代或错项目 Spec|

实施顺序：先新增有历史保护的增量迁移，开放受控的 `FIXED_REFS` 根及仅根创建事务内子行、延迟闭合集合；再在同一 CREATE 事务中于源证明之后调用 A01 资格服务，将批准快照/来源指纹纳入内容指纹并持久化固定引用；最后通过现有显式 Windows 组合做真实 HTTP/PG 验证。迁移不得追改 0178/0179 或已冻结合同。若新增历史存在则拒降，故障应关闭入口并前滚修复。该资格不等于正文语义适配、客户 Review 或章节 `spec=PASS`。

## 实施与独立验收

- 0180 在原根 Guard 上加 `FIXED_REFS` 非空声明，SpecRef 仅能在根创建的同一事务 INSERT，提交后拒补写/改写/删除/TRUNCATE；原延迟闭合函数新增 Spec 数量与连续顺序检查，未削弱 Requirement/Evidence/首次结果检查。空库升降重升和 head ORM drift 已验；真实既存 SOL-06/Section/Review 数据从 0179 降回再升到 0180 后继续可写；固定引用历史存在时拒降。
- Section CREATE 在来源证明后、写入前使用同一事务重证 A01 资格，Spec 当前批准/Review 轮次/章节祖先/共有需求的固定事实进入内容指纹。Repository 原子写根、Spec 子行、Requirement/Evidence/旧形状首次结果、Audit 与持久幂等收据；旧无声明/NONE_REQUIRED 输入和首次 201 不变。Windows 显式组合注入真实 Review 快照适配器；未注入该资格的独立组合继续失败关闭。
- Win11/一次性 PG18.6 真实 SOL-06 创建/送审/批准→Section `FIXED_REFS` HTTP 201、原 Key 精确重放、改引用同 Key 409、无效 Spec 503、跨项目 404；数据库固定一条引用/一条收据/一条 Audit、受权历史反读、缺子行提交与事后补行均拒绝。历史 0178 闭锁脚本固定到 0178 验原闭锁合同；0180 另验离线 SQL 安全合同。定向 21 项/56 子例与后端完整回归 `3901 passed, 3 skipped, 6061 subtests passed`。

兼容/回滚：新增历史不可删除或追改，不允许降回 0179；应关闭新入口并前滚修复。已知问题：新章节正文与已批准专项的语义适配、现时 `spec=PASS`、Section/Outline Review、正式公钥/安装/Gate3/Pilot/正式发行尚未验；下一项先做 Section VALIDATE Spec 维当前事实证明前置核查。
