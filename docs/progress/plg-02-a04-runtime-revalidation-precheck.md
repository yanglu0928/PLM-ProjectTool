# PLG-02-A04：运行时兼容性重验证与失败关闭Owner编码前检查

- 日期：2026-11-04
- 状态：`PASS_WITH_LIMITATION`（方案和边界确定，尚未实施）
- WBS：PLG-02-A04
- 基线：冻结Data Model V1、DB Schema V1、API Contract V1；前置A01/A02/A03均PASS_SCOPE_LIMITED
- 变更记录：CR-PLG-009；当前Migration head 0227

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-02-A04
输入基线：冻结Data Model/DB Schema/API Contract V1，CR-PLG-007/008
前置任务：PLG-02-A01、A02、A03
涉及模块：Plugin Application Owner、PostgreSQL Repository/ORM/Migration、Audit
涉及实体：PluginInstallation、PluginRuntimeValidation、EnabledOperation、operation history
涉及API：无；不挂HTTP/默认应用组合
涉及权限：受控内部actor；不替代正式数据库身份隔离
验收标准：兼容复验保留合法启用；不兼容复验在同一事务追加Validation/Audit、清除启用操作并标记INCOMPATIBLE；空/有数据迁移、并发和回滚反例由GitHub hosted PG18及全链验证
风险：陈旧环境证据、并发激活、部分事务、降级丢历史
```

## 冻结语义与缺口

- Installation状态固定为`INSTALLED / ENABLED / DISABLED / INCOMPATIBLE / RETIRED`；RuntimeValidation为`COMPATIBLE / INCOMPATIBLE`。运行环境变化导致不兼容时，必须阻止新PluginExecution且保留已发布OutputArtifact。
- A02只记录首次兼容验证；A03仅接受最新COMPATIBLE且与Installation快照一致的事实。当前无重新验证Owner，0227 Installation UPDATE触发器也不允许进入INCOMPATIBLE或更新快照。
- 0227逐operation不可变history可继续承载切换记录；不兼容Installation须清空当前enabled_operations，以释放同plugin/operation唯一索引并使现态与INCOMPATIBLE一致。

## 最小实施范围

- 新增内部RevalidatePluginInstallationOwner；通过受控证据端口核对精确Installation仍存在、Package ID/SHA一致及当前runtime快照。缺证据、摘要不符或端口失败均拒绝，不伪造兼容结论。
- 使用plugin级事务锁串行A03激活及A04复验，锁Package/Installation/现态操作并校验expected lock_version。
- 每次真实有效检查都追加一条COMPATIBLE/INCOMPATIBLE RuntimeValidation和Audit，并同步Installation当前快照/状态、操作现态、每项DISABLED Audit/history；没有请求幂等键，不以相同快照跳过新检查审计。expected_lock_version用于拒绝陈旧写入。
- COMPATIBLE：保持当前合法状态和仍匹配操作；若从INCOMPATIBLE恢复，只转为DISABLED，不自动恢复此前operation集合，须经A03重新明确启用。
- INCOMPATIBLE：标记Installation为INCOMPATIBLE并撤销全部现态operation，逐项写DISABLED history/Audit；不删除安装、Package或OutputArtifact。
- Migration 0228扩充最小Installation Owner guard，允许核验快照和INCOMPATIBLE状态的受控变更；RuntimeValidation及operation history仍只追加；Owner外写入、TRUNCATE继续拒绝。
- 无新表/依赖/公开API/默认组合；不物理安装/卸载，不执行插件。本WBS不含人工retire入口，RETired终态由后续独立任务处理。

## 风险、迁移及验收

- 风险为兼容证据与Installation快照分裂、版本切换与复验竞态、Audit/history局部提交，以及回滚丢失历史；用同plugin锁、expected lock_version、同事务及只追加守卫覆盖。
- Migration只加0228、不改既有版本；空库必须upgrade/down/re-upgrade。有PLG-02验证/operation history事实时down失败关闭，不删除历史。实际PG18验证up/down、有数据升级和反例。
- Owner Unit反例覆盖兼容、不兼容撤销/逐项Audit、恢复后DISABLED、过期版本、错包/错摘要、重复请求、Audit失败回滚与A03/A04并发；另跑backend全量/wheel及完整hosted Windows PG18/parent/A17/A34/A35/A50链。
- 所有代码测试仅在GitHub hosted Windows runner D:临时目录运行；客户数据0、外部API0、生产数据库false。上限`PASS_SCOPE_LIMITED`，不代表实机、正式信任、PluginExecution、Pilot/Gate/Release。

## 编码前检查结论

方案符合冻结状态与行为边界，DB实现需新增0228并已先登记CR-PLG-009。可进入A04实现；实施前不得写代码，未完成托管验收不得标PASS。
