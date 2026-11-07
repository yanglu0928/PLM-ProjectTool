# OUT-01-A01-P17：OutputRequest Cancel Owner PG18验收（编码前检查）

- 日期：2026-11-04
- 状态：PASS_WITH_LIMITATION；CR-OUT-013已登记，允许新增托管集成验证
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P17
- 执行环境：GitHub hosted Windows 2025 Runner 临时D盘PG18.6；本机/C盘不运行代码
- 输入：CR-OUT-012 P16实现；当前 `smoke_windows_parent_package_pg_cloud.py` 和 `validation/out-01-a01-p02-owner/verify.py`

## 单一目标

直接以PG18合成行验证P16 OutputRequest/OUTPUT_GENERATE Job cancel repositories和Owner同一UOW的状态、幂等、Audit/回滚；不改产品路由/默认组合。

## 编码前证据

- 现有Hosted smoke流程在D盘Runner临时目录清洁解包Parent，建立loopback PG18.6/pgvector、执行全部Migration，再运行P02 Output Create Owner真实PG18 validator；可复用当前临时数据库与DB runtime。
- P16 OutputRequestRepository按锁定的Output行读取Facts；Jobs Repository按Job→Lease/Attempt锁序校验Owner/type/scope/project/payload来源。整体锁序由CR-OUT-012固定为OutputRequest→Job→Lease/Attempt。
- 已发现P16传入的 `completed_at` 来自Application时钟，不能作为PostgreSQL持久终态时间源；P17将由Output Repository写入数据库clock_timestamp，并读取DB实际lock_version。
- 现有Project/User表可按P02 Validator方式创建合成用户/Project；P02 Create Owner建立符合FK及绑定条件的OutputRequest/Job，不直接拼凑无效行。
- 取消Service依赖当前认证/权限/License Port；PG集成会以仅测试合成适配器给固定Actor，专测repository/service事务。它不构成真实Session、License、Project role或正式信任证明。

## 验收设计

- PENDING：正确Project/Job/Context绑定及强版本→PG18 Job CANCELLED、OutputRequest CANCELLED、lock_version递增、Audit/receipt一份、同一幂等请求精确并发重放不重复写。
- RUNNING：创建有效当前fencing token、ACTIVE Lease和未完成Attempt→同事务两个资源CANCEL_REQUESTED；确认测试明确没有Worker终止/ACK。
- 负例：旧Output版本不改变任何持久行；跨Project/错误Job绑定/拒绝角色无业务写；Audit append异常后Output/Job/receipt/Audit都恢复。
- 事务锁序与关键测试必须由hosted Windows临时PG18实际运行；不得把父包通用PG smoke或单元SQL编译当成本项验收。
- 全workflow复验后，本项最多PASS_SCOPE_LIMITED；默认Route/正式Composition与实际Output Worker仍是后续任务。

## 迁移、回滚、秘密检查

无迁移和依赖增减；只新增Hosted验证器并在既有临时PG smoke中调用。移除调用及验证文件可回滚。Fixture只用随机UUID与虚构字段；禁止密钥、客户记录和外发。提交前通过GitHub hosted diff/secret扫描，提交后只在云端运行。

## 结论

P17前置和测试数据库路径明确，进入实现；此时尚未运行该测试、尚未关闭P17。
