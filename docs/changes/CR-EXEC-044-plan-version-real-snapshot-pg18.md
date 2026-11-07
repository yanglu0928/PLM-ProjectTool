# CR-EXEC-044：OUT-01-A01-P45 真实 PlanVersion 快照重建 PG18 验证

日期：2026-11-07  
状态：PASS_SCOPE_LIMITED（2026-11-07；Hosted run 42307444742 A17 job success）。

## 当前阶段与 WBS

Phase 2 Platform Core / Windows 11 Pilot 纵向业务链。WBS：OUT-01-A01-P45。

## 输入与编码前检查

- 前置：P41真实Plan Owner精确 project-scoped 查询 PASS_SCOPE_LIMITED；P42 Output成功事务链 PASS_SCOPE_LIMITED；P44空正式Publisher trust下的拒绝与零副作用 PASS_SCOPE_LIMITED。
- 限制：P41独立PG18探针的PlanVersion表为最小合成表，`get_current`快照由fixture提供。当前A17 Hosted Windows packaged Edge verifier已通过实际Owners/API创建Plan、PlanVersion/WBS/RequirementRefs，并把状态提交为IN_REVIEW，数据库migration及browser smoke完整；可以在同一拥有的PG18实例直接调用真实Plan Owner projection。
- 目标：在A17现有同run packaged PG18/Edge流程中，以浏览器实际创建的PlanVersion UUID调用真实 `PlanVersionReadService.read_output_source` 与 `SqlAlchemyPlanVersionReadRepository.get_current`，从迁移后PostgreSQL表重建实际WBS/依赖/里程碑/排除快照；验证项目授权、精确固定版本、字段映射和IN_REVIEW状态保真。
- 范围：只改A17验证Harness；不改产品代码、API/Schema/Migration、Workflow权限、信任清单、模板策略或数据；不调用Plugin或生成文件。
- 数据：当前A17 disposable PG18中的Synthetic PlanVersion，经真实Plan/Version Owner和Edge/API创建；无客户数据。
- 验收：真实服务 + SQLAlchemy repository调用成功；ProjectId/version UUID/state/版本号与PG事实一致；两条WBS名称及关联字段由真实行重建；跨项目读取失败且不返回投影；无 current/latest回退；fixture替身不覆盖get_current；摘要标明IN_REVIEW，不称APPROVED或可Output。
- 回滚：仅撤销验证Harness调用与marker，不动现有Plan/Output Owner产品实现。
- 执行位置：GitHub Hosted Windows Server 2025，same-run parent package及RUNNER_TEMP D盘；本机/C盘不运行。

## 风险与验收边界

若需绕过Plan Owner权限、数据库约束或以SQL覆盖审批状态，立即停止。A17 fixture此时真实Review状态为IN_REVIEW；P45只验证数据重建/授权，不宣称Policy APPPROVED可用、Output成功、正式信任、Win11实机、Pilot、Gate或Release。

## 实施及验收结果（2026-11-07）

- 在GitHub Hosted Windows Server 2025 D盘same-run disposable PG18库中，A17 packaged Edge流程实际创建的PlanVersion UUID由真实 `PlanVersionReadService.read_output_source` 与 `SqlAlchemyPlanVersionReadRepository`读取；该版本为IN_REVIEW，版本号1，真实重建两条WBS（含TASK-002及验收标准字段），值与数据库事实一致。
- 固定项目成员授权的精确版本读取成功；改用随机ProjectId时返回RESOURCE_NOT_FOUND，不泄漏投影。断言在A17验证器内执行，job成功；固定marker未单独进入受限Artifact摘要，故保留job及验证器断言作为证据，不宣称Artifact内有独立P45 marker。
- Run [42307444742](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42307444742)：A17、P25、A34以及构建/后端/前端等job成功。全run 17 jobs中16成功；唯一失败为无业务markers的SUR-07-A08 initdb 3221225781。CR-EXEC-039已停止TEMP/TMP试验，不把A08失败归因于P45。
- 仅验证合成项目与Hosted D盘；没有产品/API/Schema/Migration更改、客户数据、插件执行、文件生成或本机/C盘运行。IN_REVIEW未被视为APPROVED；不代表真实Output可用、正式Publisher trust、Windows 11实机、Pilot、Gate或Release。
- 下一项 OUT-01-A01-P46：以同一真实Owner projection检验固定Output adapter与APPROVED policy的实际拒绝及零写入，按CR-EXEC-045执行。
