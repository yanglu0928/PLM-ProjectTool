# CR-PLG-008：PluginInstallation按操作原子启用与版本切换

- 日期：2026-11-04
- 状态：编码前决定已登记；按持续自主执行授权实施，须以托管证据验收
- WBS：PLG-02-A03
- 关联：CR-PLG-007、冻结Data Model V1、SC-01/SC-02、Gate 2 API Contract V1

## 原因

PLG-02-A02只建立经核验的初始Installation事实。冻结模型还要求同一plugin_id的每个operation至多由一个Installation启用，版本切换必须原子且可审计并保留Installation历史。目前Owner关闭表及空的启停业务路径阻塞后续Output执行前的许可检查。

## 编码前增量决定：保留每个Operation的切换历史

- 独立复核发现冻结AuditEvent只允许状态/原因代码，没有operation ID字段；当前enabled_operations表表示现态并在版本切换时删除旧归属。因此仅写安装状态Audit无法在未来复原具体切换的operation集合。
- 在既定持续自主授权内，增设冻结PLG-02 Aggregate的追加式owned history表 `plg_enabled_operation_history`；每次具体ENABLE/DISABLE转换同时保存精确operation ID、安装/精确Package、actor、UTC、trace和对应Audit event ID。增加SCHEMA增量仅用于内部追溯，不改变公开API/核心Root、Permission或插件执行范围。
- 该表只INSERT、永不UPDATE/DELETE/TRUNCATE；复合FK回指Installation/Manifest operation，FK回指Audit Event。任何迁移回退只在新增history及现有PLG-02事实全部为空时允许。该冻结Data Model V1增量及风险、迁移/回滚和验收计划先记于CR，后编码。

## 决定与范围

- 新增内部Owner，接收Installation ID、非空操作集合、actor/trace及目标M-DEP lock_version。只允许Manifest声明的操作子集。
- PostgreSQL事务先取得插件级锁，再锁定目标Package/Installation、当前启用行及同plugin操作冲突的Installations。目标必须是VERIFIED且未撤销Package、状态为INSTALLED/DISABLED/ENABLED，且最新COMPATIBLE runtime snapshot与Installation当前核验快照一致。
- 一次事务把目标操作集合切到目标Installation、从旧Installation撤下冲突操作；若旧安装不再拥有其他启用操作则将其状态降为DISABLED，仍有操作则保持ENABLED。目标Installation置ENABLED；固定identity/安装事实不改，M-DEP lock_version单调递增。
- 所有行变化与对应Audit在同一Unit of Work内提交或回滚。Exact state replay为无写入幂等；过期目标lock_version拒绝；PK/Package/Manifest FK及数据库操作唯一索引保持最终保护。
- 只允许本内部Owner操作状态与owned enabled operation记录。不开HTTP API、不接默认组合、不安装文件、不改变Publisher trust、不启动插件子进程、不使Output Create可用。
- Migration `20261104_0227`把0226关闭守卫升级为受限Owner标记下的最小操作：Installation仅允许状态/Actor/时间/lock_version规定变更；EnabledOperation仅允许Owner插入/删除；RuntimeValidation仍只追加。继续拒绝TRUNCATE，任何Owner标记外的写入均拒绝。Down仅当目标表无Installation/EnabledOperation/RuntimeValidation记录时回退。
- 无冻结Data Model/API或外部依赖变化。按操作记录历史由追加Audit和不可覆盖的Installation行追溯；owned EnabledOperation表只表示当前状态。真实DB身份隔离和宿主执行信任不由本项替代。

## 风险、迁移与验证

- 主要风险为并发版本切换、操作集合部分重叠、Audit失败和runtime snapshot过期；由插件级advisory lock、行锁、lock_version、唯一索引、同事务Audit及PG18并发/回滚反例覆盖。
- 迁移向前增加revision，不改既有行或冻结表字段。Rollback只有目标事实表全空才允许；存在任何安装/启用/运行时验证历史均失败关闭。
- 用仅合成包和安装事实的GitHub hosted Windows runner D盘临时PG18/单测/全链回归验证。用户本机不运行项目代码或测试；客户数据和外部API调用为0。
- 测试失败或发现与冻结语义不兼容时，先补本CR偏差记录，再改代码。仅PASS_SCOPE_LIMITED；不宣称实际插件执行、Windows 11安装、Gate、Pilot或正式Release通过。


## CR-PLG-008正式偏差记录（2026-11-04）

- 偏差类型：冻结Data Model V1增量；原因是冻结AuditEvent只允许有限状态代码而owned当前态表不保留已移交操作明细。静默只写状态码会丢失具体operation切换历史，与“版本切换可审计”不符。
- 决定：新增`plg_enabled_operation_history`，以精确operation_id、Installation/Package引用、ENABLE/DISABLE、actor、UTC、trace和不可变AuditEvent FK保存每个操作的变化；只追加，不可覆盖/删除/清空。保持公开API、Aggregate Root、Plugin权限/信任和执行范围不变。
- 风险：多行历史需与现态变更和Audit严格同事务；由PG18原子性/Audit失败回滚/多操作切换/历史downgrade反例验证。Migration 0227降级对所有PLG-02事实表均有行时失败关闭；不重写既有0225/0226历史。
- 该差异已在编码前登记；授权依据为用户2026-09-24持续自主实施规则。需由实际托管证据验收，范围只可PASS_SCOPE_LIMITED。


## 托管验收偏差（2026-11-04，PLG-02-A03）

- GitHub hosted run 41726736924 的后端全量/wheel、前端/build、PG18/pgvector重建、父包组装、A35、A17均成功；父包 PostgreSQL smoke 在调用既有 PLG-01 schema verifier 时失败。该 verifier 的守卫数量仍按 0226 断言 17；A03 migration 0227 合法新增 3 个操作历史守卫，实际读回 20。
- 分类：验证脚本与数据库增量计数未同步，未发现产品实现失败；当前 run 整体不得标记通过。影响仅为 A03 整包父包 PG18 smoke 证据缺失。
- 修正：仅把 validation/plg-01-a01-package-schema/verify.py 的 0227 预期守卫总数更新为 20，保留三个 owner_closed 断言及其它约束，不放宽守卫检查。先登记本记录，再修改并提交验证代码。
- 重验：在 GitHub hosted runner 上重新运行完整链，要求父包 PG smoke 和 A03 migration contract均成功；禁止本机运行。未完成前 A03 状态仍为待验收。
