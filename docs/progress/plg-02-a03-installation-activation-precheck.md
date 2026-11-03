# PLG-02-A03：Plugin按操作启用/版本切换Owner编码前检查

- 日期：2026-11-04
- 状态：PASS_WITH_LIMITATION
- WBS：PLG-02-A03
- 变更记录：CR-PLG-008
- 基线提交：9624071037a32fca14f2d48ea2fea19d0cab3c64

## 冻结要求与当前缺口

- 冻结Data Model规定PluginInstallation状态为INSTALLED/ENABLED/DISABLED/INCOMPATIBLE/RETIRED；enabled_operations必须是Manifest声明操作子集，同一plugin_id每个operation最多一个Installation启用；版本切换需原子审计且不覆盖Installation历史。
- A01/A02已建立并验收三个持久表及初始安装事实Owner。当前0226只开放Installation/RuntimeValidation的受限INSERT，Installation UPDATE和EnabledOperation INSERT/DELETE仍全部关闭；没有启停业务Owner/route。
- 冻结规则中的“每操作唯一”由现有PG唯一索引兜底；版本切换还需转移目标操作集合并维护旧/新Installation状态和审计，不能通过直接delete行来伪造历史切换。

## 编码决策

- 单一命令启用一个已安装Installation的非空操作集合；仅接受Manifest中的operation ID。目标Package必须仍VERIFIED；Installation不得为INCOMPATIBLE/RETIRED；必须有最新COMPATIBLE RuntimeValidation且其脱敏快照与Installation当前validated_runtime_snapshot一致。
- 插件级事务锁串行化同一plugin_id的启用切换，接着锁Installation与现有operation行；目标Installation携带expected lock_version，旧Installation的并发由同插件锁、行锁和各自乐观锁保护。
- 只替换本次请求操作集合的唯一所有权：旧Installation仍有其他enabled operation则继续ENABLED；无剩余操作时变DISABLED。目标ENABLED；Installation身份、精确包、安装时间及历史不变。全部owner table写入与Audit同事务。
- 不新增公开API、默认组合或执行策略。由于已在CR记录Data Model V1的追加式Operation history child-table增量，本项仅扩展内部Schema；仅内部Owner/Repository与0227迁移；不安装、启用任意操作之外的能力或运行插件。
- A03偏差：需将当前数据库触发器由A02仅INSERT策略扩展为精确约束状态转移和owned operation增删；保持RuntimeValidation不可变，所有无上下文写和TRUNCATE仍拒绝。由CR-PLG-008先行登记。
- 验收使用合成Manifest/Package/Installation/RuntimeValidation，覆盖允许/禁止操作、旧/新版本部分操作交集、冲突唯一索引、过期lock_version、重复请求、并发串行、Audit失败全回滚、有/无历史降级、CI全链。无客户正文/外部服务。
- 结果只可PASS_SCOPE_LIMITED；Owner暂不挂HTTP/默认服务组合，真实DB身份/正式安装适配器/PluginExecution均未验证。

## 前置检查结果

通过有界Owner实现前置检查；没有需要用户确认的冻结基线冲突。实施与验证按CR-PLG-008执行。


## 复核发现的Audit明细缺口（编码前增量）

冻结AuditEvent字段不承载operation ID，而启用操作当前表是owned现态集合。仅写一条状态Audit会使未来切换后无法知道具体何操作被转移。故已在CR-PLG-008正式先记Data Model V1增量：新增只追加的`plg_enabled_operation_history`逐operation记录，并以FK关联Audit Event。仍不增公开API/Root/执行授权。数据表增量、风险、迁移/回滚和PG18验收先记后编码。
