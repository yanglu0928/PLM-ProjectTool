
## PLG-03-A08 受限验收完成与 P40 verifier 遗漏（2026-11-07）

- A08 独立验收由Hosted run [42362550450](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42362550450)，job 128375724422完成，日志输出 `PLG_03_A08_PG18_PASS`，结论 `PASS_SCOPE_LIMITED`。真实合成PG18.6覆盖空库/既有库0232→0233升级、单attempt downgrade/re-upgrade、多attempt rollback保护、attempt 1 RETRY_WAIT/QUEUED、attempt 2独立PluginExecution/PENDING→RUNNING、耗尽失败关闭、attempt idempotency历史、Audit失败回滚、stale fence/worker/错误码零写拒绝。Backend全量/wheel、Frontend/build、A05/A06/A07同轮通过。
- 范围限制：仅Hosted Windows Server 2025 D盘，父包合成PG18.6；未执行插件进程、未接Worker、未使用客户数据/外部服务、无正式trust或release结论。
- 同run父包PG smoke继续至 `validation/plg-02-a06-operation-disable/verify.py`，因“A08 downgrade refusal changed migration head”断言仍预期head 0232而当前head为0233失败。A08 rollback安全拒绝本身已发生；待将该验证器current-head期望更新为0233并重新执行父包smoke。P40/父包完整烟测不因此标通过。


## 第三轮 Hosted verifier 发现与修正计划（2026-11-07）

- Hosted run [42361605909](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42361605909) 中Backend全量/wheel、Frontend/build、运行时与父包组装再次通过；A06/A05/A07专项通过。A08已成功执行attempt 1重试排队、down/up、attempt 2独立RUNNING、耗尽失败及多attempt历史保留，最后读取迁移版本表时因验证器SQL使用未限定的 `alembic_version`（实际位于 `plm.alembic_version`）触发UndefinedTable。属于验收器后置断言缺陷，A08仍未关闭。
- 修正仅将A08验证器该查询限定为 `plm.alembic_version`；不变更数据库/schema/业务代码或A08验收标准。
- 同run共享父包PG smoke已通过OUT head检查，但深入PLG-01 package schema verifier后发现其 `HEAD` 常量仍写0232，导致staging数据库当前revision 0233被拒绝。修正仅将该验证器的当前head常量更新为0233，保留历史版本路径/数据与迁移断言。
- 两处脚本偏差修复后复跑Backend及父包PG smoke、A08 PG18；在专用marker出现前A08、P40不标通过。本机/C盘未运行代码。


## 第二轮 Hosted PG18 偏差与修正计划（2026-11-07）

- Hosted run [42360552157](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42360552157) 的Backend全量/wheel、Frontend/build、运行时和父包组装成功；A08专项未通过，父包PG smoke也未通过。不得以全量单测通过代替两个专项验收。
- A08专项在真实合成PG18中完成Migration、attempt 1重试排队和down/up后，第二attempt开始Execution时，`PluginExecutionStartOwner._validate` 将 claim.attempt_no 固定为1，抛出 `PLUGIN_EXECUTION_NOT_STARTABLE`。根因是Start Owner未随CR-EXEC-056已批准的逐attempt admission方案扩展；这属于产品Owner能力缺口，不是夹具问题。
- 修正计划：在保持Job类型/scope、fencing、worker、payload、绑定和PENDING状态校验不变的前提下，允许正整数attempt；补充Owner单测覆盖attempt 1/2及无效attempt；由现有Repository/Audit和真实PG18 A08 verifier确认attempt 2独立RUNNING root及后续重试完整原子性。未改代码；复验前A08不通过。
- 同run父包PG18 smoke在空库升级后读得当前schema head 0233，却由`validation/out-01-a01-p01-migration/verify.py`硬编码期望0232而断言失败。该共享验证器未随Migration 0233更新，未到P40后续验收步骤。
- 修正计划：仅将该验证器的“当前唯一head”期望更新为0233，保留向旧固定revision做升级/降级的专门断言不变；随后复跑Hosted父包PG smoke。记录为独立Harness基线遗漏，不推断P40功能失败/通过。
- 两个修正分别验证；不改API、冻结数据模型、Migration行为或Worker/ProcessHost接线，不运行真实插件/客户数据。本机/C盘未运行代码。


## Hosted Backend 首轮偏差与修正计划（2026-11-07）

- GitHub Hosted run [42359578240](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42359578240) 的Backend全量套件执行4,127项，4,126项通过，1项失败。失败为 `unit.test_migration_contract.MigrationContractTests.test_configuration_revision_follows_platform_baseline` 仍将唯一head固定断言为 `20261105_0232`；当前实际head为本CR新增的 `20261106_0233`，并非迁移运行或业务Owner失败。
- 根因：首轮同步更新了同名测试的非unit路径 `apps/backend/tests/test_migration_contract.py`，而Hosted unittest发现并执行的是 `apps/backend/tests/unit/test_migration_contract.py`；后者的动态head和revision父链断言遗漏更新。产品迁移和业务代码尚无该失败导致的修订。
- 已先记录偏差；纠正范围仅为将实际执行的unit测试预期head改为 `20261106_0233`，并将该revision的 `down_revision` 期望为 `20261105_0232`。不改变产品行为、迁移内容、Schema或业务验收。
- 后续在GitHub Hosted重新执行Backend全量/wheel及A08 PostgreSQL 18.6独立验证；只有对应断言/marker和完整迁移验收通过才关闭A08。当前A08仍未通过。测试在本机/C盘未运行。

# CR-EXEC-056：PLG-03-A08 PluginExecution 可重试失败与逐 attempt 持久化

- 日期：2026-11-07
- 阶段/WBS：Phase 2 Platform Core / PLG-03-A08
- 状态：编码前检查完成；依据持续授权进入实施，Hosted验收未运行
- 基线：PluginExecution Migration `20261105_0231`、冻结 Data Model Candidate V1、CR-EXEC-050～054、Jobs Lease 与 Output Generation Retry Owner。
- 类型：在保留各 JobAttempt 与 PluginExecution 历史的前提下，使 Output/Job/Plugin 对暂时性插件失败共享事务并允许下一次独立执行；需要可追溯 DB Schema 修订；不接 Worker/ProcessHost、不实际运行插件。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A08 可重试失败的事务收敛与逐attempt PluginExecution历史
输入基线：冻结 PluginExecution 状态模型；CR-EXEC-051 admission、052 hosted验证、053 start Owner、054 non-retryable failure Owner；既有 OutputGenerationRetryOwner/Jobs.retry_or_fail(retryable=true)。
前置任务：PLG-03-A07 PASS_SCOPE_LIMITED（run 42354245934 / job 128350519897）；同轮 Backend/wheel 与 Frontend/build通过。
涉及模块：Plugin Execution admission/failure application + repository；Output retry application入口；Jobs Lease Repository；Plugin ORM/Migration/Audit。
涉及实体：PluginExecution root/event、OutputRequest、Job/Lease/Attempt、Audit。
涉及API：无。
涉及权限：仅当前输出Job有效worker/fencing claim；Plugin安装/操作/Project/Output/Context绑定沿用既有Admission校验。
验收标准：attempt 1 transient failure 原子进入Plugin FAILED(retryable=true)、Output QUEUED、Job RETRY_WAIT，Audit/事件一致；attempt 2有独立PluginExecution root与事件；同attempt重放幂等；attempt耗尽失败关闭；旧fence/错worker/错绑定零写；Audit故障全回滚；Hosted PG18迁移与全量回归通过。
风险：冻结Migration 0231对PluginExecution设有每Job唯一，Admission只接受attempt 1，幂等键亦只按Job生成；Output retry则允许同一Job产生后续JobAttempt。保持旧Schema会让第二次执行无法记录并破坏逐attempt历史。
```

## 预提交路径校正（2026-11-07）

- 编码前检查初稿将下一 Migration 编号写为 `20261105_0232`；进一步读取当前 Alembic versions 目录及 migration_contract 后确认，`20261105_0232_output_artifact_persistence.py` 已占用该编号且当前唯一 head 为 `20261105_0232`。本任务尚未改代码或提交迁移。
- 已在编码前将本 CR 与验收计划校正为新 Migration `20261106_0233`，down_revision=`20261105_0232`；不改动已存在的 OutputArtifact migration。此编号校正已先记录后实施。

## 源码/基线发现

1. PluginExecution 数据模型将它定义为“一次隔离运行”，包含 `attempt_no`；Job拥有多条Attempt历史，OutputRequest关联0..N PluginExecution。
2. Migration `20261105_0231` 当前以 `UNIQUE(job_id)` 限制每Job仅一个Execution；Admission拒绝 attempt_no != 1，固定幂等键为 `plugin-execution:{job_id}`。
3. 既有 OutputGenerationRetryOwner 支持冻结错误码、同一Job fence下原子更新Output与Jobs至 RETRY_WAIT/QUEUED 或耗尽FAILED；A07 failure路径目前固定调用不可重试分支。
4. 因此只添加 `retryable=true` 而复用原Execution行会覆盖“单次运行身份/不可变历史”语义；保留约束则第二次PluginExecution不能持久化。

## 方案比较与选择

- A（不支持插件失败重试）：保持当前约束并把插件失败一律不可重试。改动少，但与通用Output/Jobs重试合同及冻结 attempt 历史语义不一致，暂时性故障只能人工重新生成。
- B（所选）：按 `(job_id, attempt_no)` 唯一保存单次Execution；迁移移除 `UNIQUE(job_id)` 并加入复合唯一约束；Admission允许有效attempt并按attempt生成幂等键。Plugin retry Owner复用可事务调用的Output retry与Jobs lease接口，固定允许 `OUTPUT_PLUGIN_BUSY`，原子写Output/Job/Lease/Attempt、Plugin FAILED(root/event)与两Owner Audit。每次重试建立新的Execution root，不重写旧Attempt。

选择B，因为它保持 Data Model 的单次运行历史和 JobAttempt/PluginExecution attempt 对应关系，并使用已有Output重试队列与错误码合同；不放宽插件信任或运行权限。

## 影响、迁移、回滚与验证

- Migration `20261105_0233` 只调整 PluginExecution 的 per-job 唯一键；升级不改写现有行。若down时同一Job已有多attempt记录，必须在任何DDL前拒绝降级并保留历史，不得删除数据。
- 幂等从 `plugin-execution:{job_id}` 改为 `plugin-execution:{job_id}:{attempt_no}`；同Job不同attempt各自独立，同attempt重放返回既有Execution。
- 回滚移除 retry Owner/transaction wrapper 与新Admission行为，并down Migration；若存在多attempt历史则有意阻止down，须先导出/归档并经独立数据迁移方案处理，不静默丢记录。
- 单测与Hosted PostgreSQL 18.6验证：0231→0233 upgrade、空库与既有单attempt行、attempt 1/2隔离、同attempt幂等、重试成功排队、attempt耗尽、Audit故障整体回滚、过期/旧fence与绑定错拒绝、down/up、含多attempt时down拒绝。
- Backend全量/wheel、Frontend/build与 Secret 检查；仅GitHub Hosted Windows Server 2025 D: 临时环境，不运行真实插件/Worker，不使用客户数据或外部服务。
- 不改API Contract；不宣称 Windows 11、正式trust、Gate 3、Pilot 或 Release 通过。

