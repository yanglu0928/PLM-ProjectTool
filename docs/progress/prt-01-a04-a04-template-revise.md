# PRT-01-A04-A04：Template Revise Owner

日期：2026-10-08。结论：`PRT_01_A04_A04_TEMPLATE_REVISE_PASS`。下一项：
`PRT-01-A04-A05` Template Read Owner。

## 实施结果

- 新增互不混用的PROJECT/GLOBAL修订命令；PROJECT仅ProjectManager/ImplementationMember，GLOBAL仅
  DeploymentAdmin。服务维持会话/CSRF双重授权、License、真实事务内重证与撤权后重放拒绝。
- 修订要求强`expected_lock_version`，Repository对Root加行锁，追加PUBLISHED不可变Version并固定
  `supersedes_version_id`，随后原子推进当前指针、`updated_by/updated_at`和lock version。vN满足
  `lock_version = version_no - 1`，不改写或删除旧Version/ArtifactRef。
- 复用Create的同一非执行合同、终端及Artifact规范；DocumentVersion仍由Document Owner证明Scope/状态，
  OutputArtifact Owner未实现时失败关闭。Root名称和Scope不可由修订命令改变。
- Migration0129扩展Owner guard，增加延迟修订闭包，提交时强制校验前版、当前版、Actor、完整ArtifactRef及
  唯一不可变REVISE结果；有修订历史拒绝降0128，无修订历史可恢复CREATE-only guard。
- 幂等receipt绑定Template、期望锁版本和完整规范负载；重放返回首次不可变版本结果并重证权限/License，
  新Key携带旧锁版本返回冲突。

## 验证证据

- Windows 11/PostgreSQL 18.6一次性库：空库至head、PROJECT/GLOBAL授权、License、DocumentVersion
  Scope、OutputArtifact失败关闭、PM及ImplementationMember的v1→v2→v3链、强版本、重放/冲突、Audit
  故障回滚、Root提交闭包、撤权重放、Alembic drift与历史拒降全部通过；标志
  `PRT_01_A04_A04_TEMPLATE_REVISE_PASS`。
- 定向最终26项通过；完整后端3123项通过、3项跳过；compileall通过。
- 开发wheel共1193项并包含0129、Revise Service与Repository，SHA-256
  `7282e72bf25fa24e1c791f105c38171c47f3edbc88ccd6b2a1e8710074e2ef06`。不是发行程序包。
- 首次实库运行暴露Audit摘要`vN`不符合既有受控代码合同，改为`TEMPLATE_VN`；第二次运行的GLOBAL跨Scope
  负例因沿用旧锁版本先触发VERSION_CONFLICT，验证器改用当前锁版本以到达Artifact证明。两项均完整复跑，
  未降低产品约束或篡改期望结果。
- 已对会话暴露过的凭据片段做仓库扫描，无匹配；`.tmp/`与本地wheel均未纳入提交。

## 兼容、迁移与回滚

冻结的两个Revise Operation、路径、角色和201语义不变；无公开HTTP、依赖、外发、License算法或目标平台
变化。运行回滚可停止装配Revise Service；没有REVISE历史可降0128，有历史只能前向修复，Root、版本、引用、
结果、Audit与receipt均须保留。

本轮只验证Windows 11，不能外推Windows Server 2025；Debian 13按用户指令跳过。Read、HTTP、前端、
Server 2025、Gate 3、UAT和正式发行仍开放，Gate 3保持BLOCKED。
