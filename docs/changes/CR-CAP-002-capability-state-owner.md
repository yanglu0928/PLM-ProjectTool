# CR-CAP-002：Capability 状态与元数据 Owner 守卫

- 日期：2026-10-05
- 状态：`APPROVED_BY_STANDING_AUTHORIZATION`
- 范围：`CAP-01-A05-A03`，冻结`CAP_BASELINE_PATCH`、`CAP_BASELINE_ARCHIVE`、`CAP_VERSION_RESTRICT`
- 基线：Gate 2原冻结提交`64cdf09`保留；Schema0094保持历史，不追写

## 差异与原因

冻结模型已定义Baseline的ACTIVE/ARCHIVED/RESTRICTED、Version的RESTRICTED和三个Operation，但Schema0094只允许Review正式化路径，尚无合法元数据修改、归档或限制状态转换。直接开放应用SQL会被守卫拒绝；放宽为任意UPDATE又会破坏不可变版本、正式指针和审计边界。

## 方案

追加Schema0095替换Capability守卫：Baseline只允许单次元数据更新、ACTIVE→ARCHIVED或既有Owner所需的正式指针更新；Version除既有Review路径外，只允许DRAFT/APPROVED/RETURNED/SUPERSEDED单向转RESTRICTED。APPROVED被限制时必须在同事务清空正式指针；延迟完整性保证APPROVED数量与指针精确一致。IN_REVIEW不能归档Baseline或限制Version，须先通过Review撤回/退回收敛。

限制原因使用不可变AuditEvent的受控`reason_code`保存，不向冻结Version Root增加可变字段或新业务Root。Baseline归档不撤销历史引用；归档后停止新Version、元数据及Version状态写入，需限制的Version必须先处理再归档，从而保证归档首次响应可长期精确重放。三个内部Owner统一重验Session/CSRF、DeploymentAdmin和License；Archive/Restrict使用持久幂等收据，Patch使用强ETag。

## 风险、迁移与回滚

- 风险：当前正式版被限制后ACTIVE Baseline暂时没有正式指针，普通项目成员看不到该基线；这是安全失败关闭，需另建/评审新Version恢复。
- 迁移：`0094 -> 0095`仅替换触发器函数，无表列、数据搬运、依赖、网络或客户数据变化。
- 回滚：无A03历史时可恢复0094函数；存在PATCH/ARCHIVE/RESTRICT Audit、ARCHIVED Baseline或RESTRICTED Version时拒绝物理降级，停止新命令并向前修复。
- 验证：空库降升/drift，Patch/Archive/Restrict正反路径、正式指针清除、Review冲突、幂等/并发/Audit回滚、历史拒降及全量回归。

依据用户持续授权，偏差记录完成后直接实施；该授权不改变Gate 3、正式信任、客户数据外发或发行验收要求。
