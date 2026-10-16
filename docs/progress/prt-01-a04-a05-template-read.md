# PRT-01-A04-A05：Template Read Owner

日期：2026-10-08。结论：`PRT_01_A04_A05_TEMPLATE_READ_PASS`。`PRT-01-A04`完成；下一项：
`PRT-01-A05-A01` PrototypeVersion Schema/Owner前置核查。

## 实施结果

- 新增只读Service/Repository：项目成员列表严格合并“同项目PROJECT + GLOBAL ACTIVE”模板；
  DeploymentAdmin的GLOBAL入口只返回GLOBAL，不泄露PROJECT模板。
- 当前列表以Root `updated_at + template_id`倒序keyset分页，返回固定当前不可变Version；内部固定版本读取可
  返回当前或历史Version，明确`is_current`，同时返回Root强ETag，不把历史版本冒充当前事实。
- 所有Version读取校验声明Artifact数量并按ordinal恢复固定引用；Scope、项目、Root/Version组合在SQL中同时
  限定，错误项目及GLOBAL管理入口读取PROJECT统一失败关闭。
- GET语义只用Session，不要求CSRF；PROJECT复用`PRT_TEMPLATE_LIST`的全成员读权限并锁授权事实，GLOBAL仅
  DeploymentAdmin。所有读取先验证License，失效Session、撤权、非成员与跨Scope均不返回业务对象。
- 未增加公开HTTP、表、Migration、依赖或Secret；固定版本读取是后续PrototypeVersion Owner的内部证明
  能力，不擅自新增冻结Operation。

## 验证证据

- Windows 11/PostgreSQL 18.6一次性库：真实形成两PROJECT、一GLOBAL、一其他项目模板及v1→v2修订；验证
  项目成员PROJECT+GLOBAL可见集、其他项目隔离、GLOBAL管理隔离、逐条稳定分页无重/漏、当前/历史版本、
  Root ETag、License及撤权失败关闭；标志`PRT_01_A04_A05_TEMPLATE_READ_PASS`。
- 首次夹具尝试让同一用户同时成为两个项目活跃成员，被既有`uq_prj_members__user_active`正确拒绝，改用独立
  其他项目经理；第二次将已登录非成员误期望为401，按既有防枚举合同修正为`RESOURCE_NOT_FOUND`。完整复跑
  通过，未改产品权限语义。
- 定向13项通过；完整后端3125项通过、3项跳过；compileall通过。开发wheel1195项，SHA-256
  `a82554fb1cb229320b652cd5315c08465806366267858890f989a24515bd00b8`，不是发行程序包。
- 会话已暴露凭据片段扫描无匹配；`.tmp/`和本地wheel未纳入提交。

## 兼容、回滚与未完成

冻结两个Template List Operation的Scope/角色不变；内部历史读取不暴露为新API。运行回滚为不装配Read
Service，无数据迁移或历史破坏。Windows Server 2025未由Win11结果推定，Debian 13按用户指令跳过。

Template Schema/Create/Revise/Read Owner已闭合，A04完成；HTTP仍按既定A09统一开放。PrototypeVersion、
Review、Link、HTTP、前端、Server 2025、Gate 3、UAT和正式发行仍待，Gate 3保持BLOCKED。
