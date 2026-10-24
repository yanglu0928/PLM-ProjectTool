# SOL-06-A13-P04：结构化专项当前事实与类型检查评估器

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_CURRENT_FACTS_PG_PASS`；只完成同一受锁事务内的只读事实评估，不表示授权 Service、持久收据、Audit、HTTP 或送审已实现。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P04`|
|输入基线|A13-P02 八维事实/四类检查合同；A13-P03 固定验证来源与系列 latest 身份；A08 创建时来源证明摘要|
|前置任务|纯报告合同、稳定来源读取和真实 Requirement/Section/Evidence/Document Owner 均已存在，可在共享锁事务内复验当前事实|
|涉及模块/实体|Solution；RequirementVersion、SolutionSectionVersion、DocumentVersion、Evidence 当前资格只读证明|
|涉及 API / 权限|无；评估器只消费已由上层提供的事务、Session token、TraceId 和受锁来源|
|验收标准|各 Owner 独立形成 PASS/FAIL/UNAVAILABLE；创建来源摘要可重算；系列历史明确 FAIL；四类只声明严格结构检查；缺 Owner 不虚报通过|
|风险|只检查数据库形状而忽略来源漂移；单个 Owner 异常污染其他事实；历史版本误报当前；缺 Trace/Artifact/类型业务 Owner 时伪造 ready|

## 实施结果

- 新增 `StructuredSpecCurrentFactEvaluator`，在 A13-P03 已取得共享系列锁的事务内逐项调用既有 Requirement、Section/SectionVersion、Document 与 Evidence Owner；端口异常、项目/身份/摘要不一致均只把对应事实关闭为 `UNAVAILABLE`，不把未知伪装成业务 `FAIL` 或通过。
- Requirement、Section/Document、Evidence 全部当前可证明时，按创建时 `STRUCTURED_SPEC_PROVEN_SOURCES_V1` 的准确字段和顺序重算 SHA-256；相等为 integrity `PASS`，来源内容漂移为 `FAIL`，任一来源不可证明则 integrity 保持 `UNAVAILABLE`。
- 系列最新身份由固定来源 Repository 决定：当前版本为 `PASS`，历史版本为 `FAIL`。空 Artifact 集可确定为 `PASS`；非空 Artifact 因尚无正式 Owner 保持 `UNAVAILABLE`；Trace 始终 `UNAVAILABLE`。
- 四种类型目前只声明已由严格 payload validator 证明的结构项：流程图结构、接口边界映射、迁移范围映射、权限矩阵默认拒绝分别为 `PASS`；其余真实性、完备性、可执行性或覆盖检查全部保持 `UNAVAILABLE`。因此真实当前来源可以得到 `valid=true`，但不能得到 `ready_for_review=true`。

## 验证证据

- P02～P04 联合定向：50 项通过，覆盖匹配摘要、来源摘要漂移、Owner 异常隔离、历史版本、非空 Artifact、四类型结构检查及非法上下文。
- Windows 11 / 可弃 PostgreSQL 18.6：真实 Auth、Project、Document、Requirement、Section、Evidence 与 SOL-06 v1/v2 链中，当前版本来源及摘要通过；历史版本身份失败；迁移结构检查通过；Trace 和缺失类型 Owner 为 `UNAVAILABLE`，最终 `valid=true / ready_for_review=false`。脚本退出 0，临时库/实例按既有夹具清理。
- 后端全量：`3711 passed, 3 skipped, 5791 subtests passed in 103.70s`。
- py_compile：生产评估器、单元测试和 PostgreSQL 验证脚本通过；`git diff --check` 通过。
- Python 3.13.15 开发 wheel：1405 个条目，评估器模块入包 1 份；SHA-256 `976e3914b65f9e78227cae4523da5027d68f40328288a47e2c08e58e17d7339b`。
- 首轮单元夹具使用了过短幂等键，首轮 PG 夹具未透传 Document proof 的三个依赖；均为新增测试装配问题，修正后完整重跑。随后补充“按当前证明重算创建摘要”以纠正仅凭持久化形状判断 integrity 的实现，再次完整重跑上述证据。
- 无 Migration、外部 AI/网络、客户数据或 Secret 外发。

## 兼容、升级、回滚与遗留

本项只增加未装配的应用评估器、测试与验证脚本；无 Schema、冻结 API、权限、License、依赖或旧数据变化，无升级动作。可撤新增模块；任何既存不可变专项版本不得删除。开发 wheel 不是 Pilot 或正式发行包。

受权 Service、首次收据/Audit、HTTP、Windows 平台装配、页面/Edge 尚未实现。Trace、非空 Artifact 及各类型非结构业务检查缺少正式 Owner，继续显式 `UNAVAILABLE`。正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A13-P05` 实现内部受权验证 Service：复用 Session/License/项目写策略，在同一事务组合 Repository 与评估器，首次观察持久化收据和 Audit，重放返回原观察；不接 HTTP。
