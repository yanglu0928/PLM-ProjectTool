# PRT-01-A04-A03：PROJECT/GLOBAL Template Create Owner

日期：2026-10-08。结论：`PRT_01_A04_A03_TEMPLATE_CREATE_PASS`。下一项：
`PRT-01-A04-A04` Template Revise Owner。

## 实施结果

- 新增互不混用的 `CreateProjectPrototypeTemplate` 与 `CreateGlobalPrototypeTemplate` 内部命令；PROJECT
  仅 ProjectManager/ImplementationMember，GLOBAL 仅 DeploymentAdmin。命令先完成会话/CSRF及权限重证，
  再验证 License，最终在实际事务内写入。
- 同一事务建立 Template Root、v1 PUBLISHED不可变Version、有序ArtifactRef、不可变结果、Audit与幂等
  receipt；重放仍重证当前权限和License，只恢复首次持久结果，不用请求体重建事实。
- 名称使用NFKC；布局/组件合同限制为有界JSON对象，拒绝非有限数、控制字符、已知主动内容键/标记、
  超深/超大结构。事件键使用明确列表而非笼统`on*`，避免把`one`等普通业务字段误拒绝。
- 适用终端限制为1～16个规范大写值；ArtifactRef限制为0～100个去重固定引用。DocumentVersion必须同时满足
  Version AVAILABLE、Document ACTIVE、File AVAILABLE；GLOBAL模板只接受GLOBAL文档，PROJECT模板只接受
  GLOBAL或同项目文档。OutputArtifact Owner尚未实现，引用失败关闭，不接受裸UUID替代证明。
- Migration0128只开放CREATE，增加声明Artifact计数并以延迟约束闭合Root/Version/Result；拒绝接纳0127
  Owner关闭期间的旁路历史，所有Template历史仍拒绝破坏性降级。

## 验证证据

- Windows 11/PostgreSQL 18.6一次性库：空库至head、PROJECT/GLOBAL权限、License、DocumentVersion
  Scope/状态证明、OutputArtifact失败关闭、规范合同、幂等重放/冲突、Audit故障全回滚、提交闭合、撤权后
  重放拒绝、Alembic drift与历史拒降全部通过；标志 `PRT_01_A04_A03_TEMPLATE_CREATE_PASS`。
- 定向单元最终26项通过；完整后端3119项通过、3项跳过；compileall通过。
- 开发wheel共1190项且包含0128及五个新增运行模块，SHA-256
  `9ffbb4962b645ae42ec42274a01a8df8ab5801d8db5eb1eaf49b9cd01984630d`。该wheel不是发行程序包。
- 首次离线Migration测试发现`upgrade()`访问数据库，已改为离线只生成DDL、在线才检查历史；首次真实库
  负例先由更早的复合FK拒绝而非指定闭包消息，验证器改为接受任一数据库级失败关闭并完整复跑。两项均为
  测试/迁移边界修正，未弱化产品约束。
- 已针对用户曾在会话中暴露的凭据片段执行仓库扫描，无匹配；通用Secret探测器的源码和伪造测试样例不被
  误报为真实Secret。`.tmp/`保持未跟踪且未纳入提交。

## 兼容、迁移与回滚

这是对已登记CR-PRT-001的前向兼容实现，不改变冻结HTTP、六个Template Operation、依赖、外发、License
算法或目标平台。升级到0128后才允许应用Owner创建；没有Template历史时可退回0127，存在历史只允许前向
修复。运行回滚可停止装配Create Service，但Root、Version、ArtifactRef、结果、Audit及receipt历史必须保留。

本轮仅在Windows 11验证；Windows Server 2025不能由该结果推定通过，Debian 13按用户指令跳过。Revise、
Read、HTTP、前端、Server 2025、Gate 3、UAT和正式发行仍开放，Gate 3保持BLOCKED。
