# PLG-02-A05：Installation退役终态Owner编码前检查

- 日期：2026-11-04
- 状态：`PASS_WITH_LIMITATION`（实施范围确定，尚未编码/验收）
- WBS：PLG-02-A05
- 变更记录：`docs/changes/CR-PLG-010-plugin-installation-retirement.md`
- 前置：PLG-02-A01/A02/A03/A04均以`PASS_SCOPE_LIMITED`完成

## 检查结论

A01冻结持久状态集合已包含`RETIRED`，A02初始事实Owner只建立经验证的安装事实，A03拒绝对已退役Installation启用，A04拒绝对已退役Installation运行时复验。A04 precheck明确要求将终态退役放在后续独立WBS。冻结现有数据结构含当前操作表、不可变逐操作历史、RuntimeValidation和AuditEvent，足以表达退役，不需新增Root/API/业务表。

编码前决定：新增一次性内部退役Owner。通过同一plugin级锁和Installation行锁协调A03/A04；expected_lock_version拒绝陈旧命令。命令先逐项清除当前启用操作并为每项写DISABLED History/Audit，再写Installation级退役Audit、状态RETIRED及新lock_version；所有事实在同一事务提交。空操作安装同样写Installation退役Audit。RETIRED拒绝再次退役、启用和复验。

Migration 0229仅扩充受控状态变更guard，不扩展数据库模型/API。历史/Package/Installation/Audit/既有产物均保留。物理卸载及删除不属于本项；不执行插件或开放生产组合。

## 编码前检查

- 冻结状态/引用：Installation状态允许值和Package引用保持不变；RETired只作单向终态，既有精确Package和runtime快照不篡改。
- 审计与历史：有操作时每项产生一条DISABLED历史及Audit，Installation产生RETIRE Audit；事务失败时三者与现态操作均回滚。
- 并发：A03/A04同一plugin锁，逐Installation锁；expected version解决陈旧调用。已退役对象拒绝重放，不因相同输入伪装成幂等成功。
- Schema/Migration：新增0229；只调节Installation更新守卫；不增加ORM字段/表。空库升降重升，有任何PLG-02事实时禁止降级。
- 主要风险：遗漏操作撤销、历史/审计部分写入、激活/复验竞态、误将退役视为物理卸载。通过多操作PG18 smoke、审计故障回滚及明确不执行文件/子进程验证降低风险。
- 验收：定向Owner反例、后端全量/wheel、ORM/Migration契约、PG18升级/降级保护、父包PG生命周期及A17/A34/A35/A50完整云端链。
- 执行环境：仅GitHub hosted Windows runner D:临时目录；不在用户本机/C盘运行代码或测试。

## 前置差异与限制

按A04 CR已排除的“人工retire终态”独立建立A05；不改变冻结状态枚举，也不复用A04不兼容事件来代表人工退役。Migration 0229属于经用户持续授权、先记录后实施的DB guard增量；风险与可回滚条件已在CR-PLG-010中登记。

本项通过后最高为`PASS_SCOPE_LIMITED`，不等于实际安装器、公开API、生产授权、插件执行或Windows 11实机验收。


## 托管验收结论

PLG-02-A05以`PASS_SCOPE_LIMITED`完成，证据详见`plg-02-a05-installation-retirement-result.md`。Migration 0229的真实PG18 guard、退役审计要求、RETIRED终态和有数据降级保护均通过同run smoke。该结论不覆盖物理卸载/API/默认组合/PluginExecution或Pilot/Gate/Release。
