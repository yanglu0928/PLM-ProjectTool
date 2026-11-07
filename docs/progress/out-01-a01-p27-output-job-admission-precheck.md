# OUT-01-A01-P27 编码前检查：Output 执行前请求与快照绑定

- 日期：2026-11-05
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P27
- 结果：**PASS_WITH_LIMITATION，可开始编码**
- Change Request：CR-OUT-023

## 编码前检查

- 当前Phase：Phase 2 Platform Core；Gate 3 尚未通过。
- 当前问题：为未来Output消费者提供只读准入校验，确认claim严格绑定至同一项目的OutputRequest/ContextSnapshot，并在当前时刻重新读取插件operation能力。
- 代码基线：Gate 2冻结版本及当前受追溯的增量；Jobs claim隔离为CR-OUT-022/P26。无Schema、Migration、公开API或默认App挂载修改。
- 核对的源码契约：
  - `jobs/application/output_enqueue.py` 与 `jobs/infrastructure/output_enqueue_repository.py` 在同一caller事务写入 OUTPUT_GENERATE Job 及精确的output_request_id/context_snapshot_id refs。
  - `output/infrastructure/orm.py` 持久化OutputRequest的job_ref/project_id/context_snapshot_id/output_type/plugin_operation/state，以及项目隔离的不可变ContextSnapshot和fingerprint。
  - `output/application/resolve_context.py` 创建时解析固定来源并校验模板/策略/插件能力；`plugin/application/operation_capability.py` 提供当前enabled/trusted/output_types投影。
  - 不存在Output Worker；P26只建立专属claim，不执行插件。当前创建期的校验不足以防止入队后能力撤销。
- 编码边界：一个只读Output准入Owner/Repository及其fail-closed测试。校验job类型/project/payload refs、request.job_ref/request.context_snapshot_id、snapshot project/source refs/fingerprint和当前插件operation enabled+trusted+output_type。错误时拒绝；成功只返回最小身份事实。
- 不纳入：lease/fencing副作用执行、请求状态变更、运行时装配、文件/Artifact生成、插件子进程、API/Schema/Migration。
- 风险与回滚：check之后lease可能过期，因此结果仅为准入事实，不是可无限期持有的执行授权；未来Worker必须在副作用边界复验活动lease/fencing和信任。撤回新Owner/Repository即可回滚，数据库不变。
- 验证：先跑新增定向单测，再在GitHub hosted Windows Server 2025 runner D盘用synthetic PG18验证正确绑定和错绑/能力撤销拒绝，后跑后端回归及流水线。不得在用户本机或C盘执行。
- 独立阻塞：P25 initdb仍以0xC0000135失败，未启动真实HTTP/Edge；本WBS沿用可工作的父包PG smoke隔离验证，不把其结果表述为P25通过。
- 结论：前置基线/范围/变更控制/验证/回滚已齐全，编码可开始，结论限于准入校验本身。
