# CR-PLG-010：PluginInstallation受控退役终态Owner

- 日期：2026-11-04
- 状态：编码前已登记；按持续自主执行授权实施，须以GitHub托管证据验收
- WBS：PLG-02-A05
- 基线：冻结Data Model V1、DB Schema V1、API Contract V1，以及CR-PLG-007/008/009

## 原因与冻结约束

PLG-02状态集合已包含`RETIRED`，但A03启用Owner和A04复验Owner均失败关闭排除该状态；A04编码前结论明确把人工退役终态留给后续独立WBS。现有逐操作EnabledOperationHistory可记录移除当前启用操作的DISABLED事实，AuditEvent可追溯Installation和operation变化，无需增加Root或公开API。

## 决定与范围

- 新增仅供内部组合调用的Installation retirement application Owner/repository，不接HTTP/API、默认生产组合或物理安装器。
- 明确一次性终态命令：要求Installation精确ID、actor/trace和expected lock_version；仅允许非RETIRED现态。已RETIRED、找不到对象、陈旧版本及不合法事实均拒绝，重复退役不产生额外成功审计。
- 若现态有启用操作，同一事务逐项删除EnabledOperation，追加对应DISABLED history与Audit；随后追加Installation RETIRE Audit并将状态改为RETIRED、lock_version递增。若当前无启用操作仍保留Installation级Audit并进入RETIRED。
- 退役不执行文件系统卸载，不删除PluginPackage、Manifest、Installation、Validation、History、Audit或既有OutputArtifact；不恢复/自动迁移操作集合。RETIRED不允许A03重新启用或A04复验恢复。
- 新增Migration `20261104_0229`仅扩充Installation Owner guard以约束受控单向RETIRED变更；保留所有表/字段和追加式历史策略。无新实体、API、外部依赖或冻结根模型变更。

## 风险、迁移与回滚

- 主要风险：操作集合未全部撤销、Audit/History/Installation状态局部提交、并发A03激活/A04复验造成竞态、错误退役/已退役重放。
- 继续使用与A03/A04相同plugin级事务锁，锁定Installation/当前操作行，强制expected_lock_version，在一个UnitOfWork内执行全部事实变化。
- Migration 0229只向前增加。空库允许降级/重升；任一PLG-02安装/操作/运行验证/历史记录存在时降级失败关闭，不删除事实。代码回滚不回滚已经写入的RETIRED事实；不执行生产退役。
- 验证覆盖无操作/多操作/单操作退役、每操作历史与审计、陈旧版本/并发竞态、重复退役、Audit写入失败全回滚、owner外写/截断拒绝、空库升降重升及有事实拒绝降级，并跑完整GitHub hosted链。

## 验收边界

- 仅合成托管数据、GitHub hosted Windows runner D:临时目录与PG18；客户数据0、外部API0、生产数据库false。
- 不进行真实安装/卸载、插件启动或执行，不开放API/默认组合，不代表Windows 11实机、正式信任、Pilot、Gate或Release通过。
- 失败先在本CR记录偏差，再实施修复；结论不超出`PASS_SCOPE_LIMITED`。
