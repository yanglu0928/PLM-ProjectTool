# CR-PLG-010：PluginInstallation受控退役终态Owner

- 日期：2026-11-04
- 状态：已完成；GitHub hosted run 41743782405 全13/13 jobs成功，结论 `PASS_SCOPE_LIMITED`
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


## 验收结果（2026-11-04）

- 代码提交：`358483d626c88a1e9ef1ccfcdf3e99de7db7546c`；GitHub hosted run [41743782405](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41743782405) 与分支head一致，13/13 jobs成功。
- 后端全量3,955 tests及wheel、前端测试/typecheck/build、PG18/pgvector sidecar、嵌入式后端/父包组装通过。PG smoke artifact 13283431324 报告PostgreSQL 18.6、schema head 0229、`installation_retirement_guard=PASS`、空库升级/降级重升和存在PLG-02事实时降级拒绝；退役要求关联INSTALLATION_RETIRED Audit且无活动操作，RETIRED后拒绝改回。
- 同一run父包候选SHA-256 `81b1425c2ffa866f43b96ebc744bec0cbef8332b090c9d7cab746dc58e016515`，20,173 files，D盘托管临时区清洁解包验证通过。A17 artifact 13283911131：29个HTTP调用、PlanVersion审核状态IN_REVIEW、客户决定数0；仅synthetic Windows Server 2025 hosted runner。A34 artifact 13283696477：失败候选隔离、4个持久marker保留、显式人工恢复通过；升级后产品启动仍按正式公钥/License/数据库凭据/服务ACL/TLS阻断，产品服务没有启动。A35与A50成功。
- 范围上限`PASS_SCOPE_LIMITED`。不接公开API/默认组合/真实安装适配器，不物理卸载，不启动或执行插件；不构成Windows 11实机、正式信任、Pilot/Gate/Release验收。
- 下一项：PLG-02-A06 生命周期受控组合与宿主适配器编码前检查；按冻结API、真实安装身份及信任边界先行核对。
