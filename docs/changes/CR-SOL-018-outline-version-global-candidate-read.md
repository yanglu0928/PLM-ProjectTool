# CR-SOL-018：OutlineVersion 项目成员选择 GLOBAL 参考候选的只读边界

日期：2026-10-09。状态：实施前登记，依据 CR-EXEC-001 持续授权分析与实施；不追写 Gate 2 冻结提交 `64cdf09`。TraceLink：冻结 API-04 `SOL_OUTLINE_VERSION_CREATE` → CR-SOL-016/017 → P05 双 Scope 服务端 CREATE → 本 CR → 项目角色安全候选读取 → P06 页面/浏览器。

## 冲突及证据

冻结 CREATE 允许本项目 ProjectManager/ImplementationMember 引用当前 ELIGIBLE 的 PROJECT 或 GLOBAL ReferenceVersion，服务端 Owner 已可重证两种 Scope。现有 `/api/v1/global/reference-solutions` 列表/详情通过 `GlobalReferenceReadService.AdminPort.authorized_admin` 仅允许部署管理员，不能作为项目成员的候选数据源。把项目用户伪装成管理员、复用管理员会话或让用户手填 GLOBAL UUID，均破坏权限边界、来源可核查性和操作体验。该缺口仅影响浏览器候选选择，不否定已验的受控后端 GLOBAL CREATE。

## 方案与选择

- 不选择开放现有 GLOBAL 管理列表/详情给所有项目成员：详情含来源元数据，权限扩大过度。
- 不选择裸 UUID、静态导入表或前端缓存管理员结果：缺现时资格、无法安全核查来源。
- 选择新增项目上下文中的最小 GLOBAL 候选只读投影：先验证本项目当前成员的 Solution 写资格与 License；只返回当前可供候选的 GLOBAL 根/版本固定 ID、合规展示名、版本号与状态，不返回客户来源、正文、Locator、脱敏证据或管理员凭据。服务端最终 CREATE 仍重新证明当前资格、来源和人工确认；候选列表不是正式业务事实。需另行确认 GLOBAL 合规展示名的可见性与分页/游标签名密钥边界，缺其中任一证明时失败关闭。

## 差异、风险、迁移/回滚与验证

这是相对现有管理员专用只读 API 的最小新增读面；不改旧 API、CREATE 路径/角色、数据模型、Schema 或 License。若投影名仍可能含敏感信息，则降为经审定的非敏感显示标签；不得猜测/泄露。无 Migration；新路由默认不挂载，可关闭新读面回滚，历史 CREATE/审计不可删除。验证计划：项目 PM/IM 正例、Customer/暂停/跨项目/License 拒绝、GLOBAL 资格撤回/确认过期/旧版本不可见、列表分页/重放/响应不含敏感字段、Win11 ASGI/PG 与浏览器；正式服务账户、Server2025 与 Gate3 独立验收。

在该读面通过前，P06 页面只能安全选择本项目 Section、当前批准 RequirementVersion 和 PROJECT ReferenceVersion；GLOBAL 选项保持不可提交，不能把项目内子集报告为完整 P06 PASS。Debian13 实机依用户指令跳过。
