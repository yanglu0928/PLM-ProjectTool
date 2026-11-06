# CR-EXEC-045：OUT-01-A01-P46 真实 PlanVersion 状态门与 Output 零写入验证

日期：2026-11-07  
状态：编码已完成；Hosted PG18/A17验收待完成（2026-11-07）。

## 当前阶段与 WBS

Phase 2 Platform Core / Windows 11 Pilot 纵向业务链。WBS：OUT-01-A01-P46。

## 输入与编码前检查

- P45（CR-EXEC-044）已在 Hosted A17 same-run PG18中通过真实 `PlanVersionReadService` / `SqlAlchemyPlanVersionReadRepository` 重建 packaged Edge/API生成的PlanVersion；ProjectId/UUID精确，状态为 `IN_REVIEW`，两条WBS已持久化重建，跨项目读隐藏。
- P42（CR-EXEC-041）已用合成APPROVED来源验证真实 `TrustedOutputContextResolver` 与 `OutputRequestService` 的事务写入链；P44（CR-EXEC-043）已用实际空Publisher keyring和真实PG capability repository验证trust缺失时零写入拒绝。
- 源码确认生产 `FixedOutputSourceAdapter` 会调度真实Requirement/Plan Owner projections；固定Plan DOCX策略的 `allowed_review_states` 仅为 `APPROVED`，resolver在source校验中拒绝其他状态。此前P45证明当前A17 PlanVersion真实状态为 `IN_REVIEW`，但该真实Owner投影尚未穿过生产FixedOutputSourceAdapter和Output状态策略。
- 任务目标：在A17 same-run迁移后PG18中，以该固定IN_REVIEW版本经实际Plan Owner读层、生产 `FixedOutputSourceAdapter`、内置不可变Plan模板与APPROVED策略、真实 `TrustedOutputContextResolver` 和 `OutputRequestService` 发起合成请求；该请求必须在Owner状态门失败，且OutputRequest、ContextSnapshot、Job、Outbox、Audit、Idempotency六类记录前后计数不变。

## 范围、测试夹具与验收

- 仅修改A17验证Harness；不改产品逻辑、API、Schema、Migration、审批状态、授权模型、Publisher trust或打包文件。
- 使用合成session/CSRF、Actor/Project、固定source/template/policy及测试License/Access。仅为使resolver走到真实Plan Owner与状态门，可提供 test-only enabled/trusted capability；清晰标记为测试夹具，绝不调用PluginService、子进程、文件生成或外部API。
- Requirement来源端口对该Plan UUID返回无匹配结果；Plan端口必须使用实际 `PlanVersionReadService`。不得构造/替换APPROVED projection或伪造Project成员权限。
- 断言Output Create拒绝；拒绝码按产品已定义行为核对；六类Output写入计数完全不变；插件执行数及外部调用数为0；source adapter实际Plan读取恰好被触发；Project/Version/state仍与P45 PG事实相符。
- 结果摘要显式导出固定P46 PASS marker，弥补P45验证断言未进入bounded Artifact摘要的可观察性缺口，但不得放宽摘要字段白名单。
- 只在GitHub Hosted Windows Server 2025 D盘 `RUNNER_TEMP` 运行，使用同run package和临时PG18；不在本机/C盘运行。
- GitHub分支为PR #61的 `feature/p51-a33-launcher-checksum-recovery`；先检查远端head、Secret，再提交并推送。

## 风险、回滚与关闭条件

若Output请求在Owner source读取前因其他门失败，或需要改写真实Review/Project状态、绕过冻结策略、使用真实Publisher密钥/插件或改变API/Schema，立即停止并记录，不得声称P46已覆盖Owner状态门。失败时只调整本次Harness，并先登记偏差；不重复CR-EXEC-039已停止的A08 TEMP/TMP试验。

回滚仅移除P46 Harness装配、断言和marker，保留P45证据及产品代码。无客户数据、付款、生产写入或不可恢复动作。


## 实现状态（2026-11-07）

- 已按编码前检查，仅扩展A17验证Harness：把同run真实Plan Owner读层接入生产 `FixedOutputSourceAdapter`、固定Plan模板/APPROVED策略、`TrustedOutputContextResolver`及`OutputRequestService`；用test-only enabled/trusted capability使请求到达真实来源状态门，不调用插件。
- 在A17受限结果marker allowlist中显式纳入P45/P46两个固定marker，令PG18 Owner snapshot及零写入断言可在bound summary中追溯。代码已同步至PR #61分支；Hosted验收待完成。
