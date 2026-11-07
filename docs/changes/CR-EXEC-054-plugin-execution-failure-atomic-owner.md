# CR-EXEC-054：PLG-03-A07 PluginExecution 不可重试失败原子终态Owner

- 日期：2026-11-07
- 阶段/WBS：Phase 2 Platform Core / PLG-03-A07
- 状态：编码前检查完成；实施与Hosted PG18验收待执行
- 基线：冻结 PluginExecution Schema/Migration 20261105_0231；CR-EXEC-051/052/053；CR-OUT-026；Jobs Lease 与 Output failure contracts。
- 类型：为PluginExecution的不可重试失败补齐跨Owner共享UoW衔接；不改Schema/Migration/API/默认组合，不接Worker/ProcessHost。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A07 PluginExecution RUNNING→FAILED 原子收敛
输入基线：PluginExecution冻结状态/事件模型；A05 admission、A06 start Owner；CR-OUT-026既有OutputGenerationFailureOwner；JobLeaseService/Repository.retry_or_fail(retryable=false)。
前置任务：A05/A06均PASS_SCOPE_LIMITED；Backend/wheel与Hosted PG18前置通过。
涉及模块：Plugin application/infrastructure；Output failure Owner/Repository事务入口；Jobs/Lease/Audit。
涉及实体：PluginExecution root/event、OutputRequest、Job/Lease/Attempt、Audit。
涉及API：无。
涉及权限：使用与Output相同的当前Job worker/fencing claim；Output必须为同绑定GENERATING，PluginExecution必须为同Project/Job/attempt/OutputRequest/Context的RUNNING。
验收标准：固定错误码白名单、仅retryable=false；Output Owner、Jobs retry_or_fail、PluginExecution FAILED root/event与两类Audit共享同一UoW。任一Audit/Owner错误全回滚。stale/mismatch/PENDING/非白名单/已终态零业务写。Hosted PG18与Backend全量/wheel通过。
风险：Output failure Owner当前自己创建/提交UoW，需先增加保留旧包装的transaction-scoped入口；必须保持Output→Jobs→Plugin锁顺序并复用Output Owner，不能让Plugin直接写Output/Jobs ORM。SYSTEM Audit actor仅合成组合，不代表Worker身份/生产信任。
```

## 方案、边界与回滚

- PluginExecution错误码沿用CR-OUT-026允许的三个固定值：OUTPUT_GENERATION_FAILED、OUTPUT_PLUGIN_UNAVAILABLE、OUTPUT_VALIDATION_FAILED；不接受自由文本、异常详情或客户正文。
- 事务先复用OutputGenerationFailureOwner：锁Output、核验绑定与当前fencing，调用Jobs retry_or_fail(retryable=false)并将Output置FAILED；随后Plugin Owner以同事务锁定Execution，置FAILED/完成时间/错误码/retryable=false/lock_version，追加FAILED事件与UNRESOLVED主体Audit；最后一次提交。
- Plugin状态/事件触发器仅在已验证后打开transaction-local owner GUC。任一Plugin写入/Audit失败须回滚Output与Job。
- 只使用合成PostgreSQL 18.6、合成worker reference与测试Actor UUID；不启动插件、Worker或服务，不创建文件/Artifact，不发送外部API。
- 回滚移除transaction-scoped wrapper与新增Plugin Owner/Repo/测试/verifier/workflow步骤；无Schema/Migration/业务数据迁移。
- 验收：真实Output GENERATING、Job RUNNING claim与Plugin RUNNING联动成功/回滚两条PG18事务；Backend全量/wheel及Secret scan。只在GitHub Hosted Windows Server 2025 D盘执行。
