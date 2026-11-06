# CR-EXEC-044：OUT-01-A01-P45 真实 PlanVersion 快照重建 PG18 验证

日期：2026-11-07  
状态：编码前检查通过；实现与 Hosted PG18/A17 验收待完成。

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