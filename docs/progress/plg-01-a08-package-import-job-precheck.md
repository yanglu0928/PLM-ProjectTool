# PLG-01-A08：受控插件包流式暂存与异步验证Job接入编码前检查

- 日期：2026-11-03
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT
- Phase/WBS：Phase 2 / PLG-01-A08
- 变更追踪：CR-PLG-006
- 前置：PLG-01-A01～A07 PASS_SCOPE_LIMITED；Gate 2基线不变
- 执行环境：GitHub hosted Windows Server 2025 runner D盘临时工作区；仅合成包/测试key，不用本机C盘或客户数据

## 编码前检查

|检查项|证据与结论|
|---|---|
|当前Phase|Phase 2 Platform Core；Gate 3未通过。|
|当前WBS|接通API-03冻结PLUGIN_PACKAGE_IMPORT的受控stream→私有持久staging→verification Job/Outbox。|
|输入基线|API-03规定DeploymentAdmin、Session/License/CSRF/Idempotency/Audit，202 JobRef及流式签名包；DM-04要求JobView不暴露payload/路径；ADR-005/007与A07/A06边界不变。|
|前置任务|PLG-01-A01～A07限定范围通过；Document两阶段bounded streaming/private LocalFileStorage及Jobs transactional Outbox已有实现；Plugin import route/queue adapter不存在。|
|涉及模块|plugin API/application/infrastructure；复用Document受限stream/storage边界但不引入Document业务身份；jobs enqueue/Outbox；auth/License/Audit显式组合。|
|涉及实体|PluginPackage metadata不改；Job/Outbox复用；必要时新增只含opaque upload ID、SHA-256、size、state/time的PackageImport staging metadata。禁止存路径、包正文、私钥或客户正文。|
|涉及API|只实现冻结 POST /api/v1/admin/plugins/packages:import，响应202 JobRef，不更改API-03。|
|涉及权限|DeploymentAdmin + Session + License + CSRF + Idempotency + Audit；应用只进入显式安全组合。|
|验收标准|最大256MiB bounded streaming、逐块摘要、Job/Outbox/Audit同事务、幂等重放/摘要冲突、文件和DB失败补偿、Outbox重复投递安全、无路径/正文泄漏；PG18及全链路hosted验收。|
|风险|文件系统/DB不能跨介质原子；停机产生孤儿；慢/超大流；reparse/path traversal；重复Job。按CR-PLG-006 opaque同卷staging、逐块hash、事务Outbox、精确失败补偿和受限孤儿检查控制。|
|迁移/回滚|若需Schema则新增migration；停用producer/route并保留Audit/Job/历史，禁止级联删已登记数据。|
|GitHub/Secret|已检查当前feature分支head；全部程序、测试、说明只同步至该分支，提交前执行secret审查。|

## 实施候选文件

- Plugin bounded staging/Application Owner、SQLAlchemy ORM/repository/migration（仅当既有数据模型不足）
- 可选Plugin Router及显式production/test composition
- Jobs Plugin enqueue adapter与hosted PostgreSQL smoke verifier
- CR-PLG-006、STATUS.md、CHANGELOG.md及最终结果文档

## 不在本任务

不安装/启用/运行插件，不增加package list/get/revoke，不引入真实发布者key，不向AI/第三方发送包，不宣称正式信任、Win11设备验收、Gate/Pilot/Release通过。
