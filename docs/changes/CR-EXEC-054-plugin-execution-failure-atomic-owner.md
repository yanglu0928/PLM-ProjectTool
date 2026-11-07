# CR-EXEC-054：PLG-03-A07 PluginExecution 不可重试失败原子终态Owner

- 日期：2026-11-07
- 阶段/WBS：Phase 2 Platform Core / PLG-03-A07
- 状态：PASS_SCOPE_LIMITED（2026-11-07，GitHub Hosted PG18.6专项验收通过；整轮workflow因独立A08失败未全绿）
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

## 实现同步（2026-11-07）

- 新增PluginExecution不可重试Failure Owner/Repository；复用既有OutputGenerationFailureOwner与Jobs retry_or_fail(retryable=false)，同一UoW完成Output/Job/lease/attempt/Plugin root/event/Audit。
- 为保持旧Output standalone行为不变，增加fail_in_transaction事务入口，原fail()仍负责单独UoW和提交。
- 固定复用三个Output错误码，不保存异常正文；锁顺序Output→Jobs→Plugin；Audit失败回滚整体。无API/Schema/Migration/Worker/ProcessHost/生产组合变化。
- 单元测试、父包PG18.6验收器及Hosted Windows job已接入；等待该提交的Hosted专项、Backend全量/wheel及相关回归结果。A07当前未PASS。
## 首轮 Hosted 验收偏差（修复前登记，2026-11-07）

- run 42352260652 的A07专项job 128344614988完成PG18临时环境与合成数据准备后，在调用Output/Plugin状态Owner之前抛出NameError：验证器未导入 OutputGenerationStartOwner；因此没有执行A07状态转移，也不能判定产品Owner通过/失败。
- 修复计划：仅补齐验收器中既有Output start Owner及Repository导入，保持业务代码、数据库Schema、验收标准、锁顺序及业务行为不变，再运行新Hosted提交的Backend全量/wheel及同一父包PG18 A07专项。
- 合成fixture在临时数据库内被本job清理；没有客户数据、插件子进程、外部调用或产品业务状态转换。A07仍未通过。
## 第二轮 Hosted 验收偏差（修复前登记，2026-11-07）

- run 42353151341 的A07专项job 128347507564中，PG18 fixture已准备，补齐导入后进入既有 OutputGenerationStartOwner，但其固定错误码 OUTPUT_START_NOT_ELIGIBLE 拒绝当前验收claim。A07 Failure Owner尚未调用，不能据此判定A07产品实现通过或失败。
- 源码与Harness对照发现：验收器手工构造 ClaimedJob，而生产Output start前置应验证 Jobs Repository签发的当前claim。具体拒绝原因尚未由固定错误暴露，不能假定插件/Output产品缺陷。
- 修复计划：只读核实 P30 已通过的PG18 Harness如何取得并传递 claim，以及 Output start 的校验条件；在已登记范围内对齐合成fixture到真实Jobs claim_next_output返回值，然后从干净PG18临时库重跑A07。不得放宽Owner校验或伪造lease字段。A07仍未通过。
### Read-only diagnosis and corrected remediation plan (2026-11-07)

- `OutputGenerationStartOwner` and `OutputGenerationFailureOwner` consume the transaction-scoped `check_output_claim(transaction, ...)` / `retry_or_fail(transaction, ...)` port. The verifier passed `JobLeaseService`, whose public methods open their own UoW and do not accept a transaction argument; the resulting TypeError is intentionally normalized to OUTPUT_START_NOT_ELIGIBLE. P30's passing harness passes `SqlAlchemyJobLeaseRepository` directly.
- The manual claim itself is not shown invalid: PLG-03-A06 already used the same `_seed` plus canonical UUID claim shape and the live Job lease proof passed. The earlier proposal to replace it with a second Jobs claim API is therefore superseded.
- Correction: instantiate one `SqlAlchemyJobLeaseRepository`; pass that repository to Output start/failure Owners, and retain `JobLeaseService` for Plugin admission/start Owners that require transaction-scoped Application methods. No Output/Jobs/Plugin contract or validation is loosened. Then rerun from a fresh hosted PG18 fixture.

## 第三轮 Hosted PG18验收结果（2026-11-07）

- run [42354245934](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42354245934)，A07 job 128350519897成功输出 `PLG_03_A07_PG18_PASS`，结论 `PASS_SCOPE_LIMITED`。同轮验证了Output/Job/Lease/Attempt/PluginExecution原子失败、事件和Audit、Audit失败整体回滚，以及stale fencing/错误worker/错绑/非白名单码零写拒绝。
- Backend全量测试与wheel、Frontend测试/build、A05/A06、P25/P40、A17、A34/A35、P24/P39/A50等作业成功；20个Jobs中19成功。唯一失败是独立SUR-07-A08，`initdb.exe`退出3221225781，TEMP/TMP只读探针同码、未应用替代环境且无业务marker。按CR-EXEC-039停止该假设路线；本workflow不能标全绿。
- 无API/Schema/Migration/Worker/ProcessHost变化，未执行插件、客户数据或外部调用；本机/C盘未运行。Windows 11实机、正式trust、Gate 3、Pilot和正式Release未通过。
- 结果详见 [PLG-03-A07 Hosted验收结果](../progress/plg-03-a07-result.md)。首轮和第二轮仅为Harness错误，不构成业务Owner失败结论，历史偏差记录保留。
