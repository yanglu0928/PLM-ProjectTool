# PLAN-01-A04-P05-A03：Windows 11 Edge 真实 Plan 身份页面验收

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：Windows 11 内部合成验收通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A04-P05-A03`|
|输入基线|Plan A04-P04 Windows/PG HTTP、P05-A01客户端、P05-A02页面/导航与既有可弃 Edge/PG 验证模式|
|前置任务|前端155文件1846项/typecheck/build通过，实际Edge交互未验；合成License允许功能验收但不等于正式信任|
|涉及模块/实体|一次性 Win11 验证脚本与文档，不改产品API/Schema/权限/License|
|涉及 API|真实浏览器通过生产Vue调用冻结 Plan CREATE/GET/LIST，后端经 FastAPI/Uvicorn/可弃 PostgreSQL 18.6|
|涉及权限|经理创建/详情/列表，客户成员只读且无创建入口；跨项目界面清屏，Session/CSRF/License仍由服务端检查|
|验收|Edge真实导航、丢失201后同Key恢复、唯一Plan/审计、列表/详情、客户创建隐藏、跨项目清屏、临时资源清理；完整运行退出0|
|风险|测试口令/合成密钥外泄、浏览器夹具误清用户资源、页面显示测试信任为正式发行、一次性测试误当UAT|

仅使用一次性合成账户、可弃库和私有 Edge profile；不外发客户数据、不供给正式钥、不触碰用户现有 `.tmp/`。

首轮实际 Edge 发现详情 GET 未发起：PlanReadClient 把浏览器原生 `fetch` 作为对象方法调用，触发非法 receiver 后被安全映射为不可用。已在同一 WBS 修正为脱离客户端对象调用，并增加显式 receiver 回归测试；原首轮不能算 PASS，须完整重跑。

## 独立验收与结果

- 修正后完整重跑退出 0，输出 `PLAN_01_A04_P05_A03_EDGE_PG_PASS`。真实 Windows 11 Edge 使用生产 Vue 静态构建、FastAPI/Uvicorn 和可弃 PostgreSQL 18.6；首个 CREATE 的 HTTP 201 被浏览器侧故障注入丢弃，页面保留操作号；重载、重新登录后按同号重试进入真实详情。
- 实际 GET/LIST 显示未审批的当前 Plan 身份，50 条较早合成身份加本次创建共 51 条跨两页；客户角色无创建入口、服务端 POST 返回 404；切换到无权项目后旧 Plan 内容清除。数据库确认本次创建仅 1 条 Plan 和 1 条 `PLAN_CREATED` 审计。一次性 Edge profile、服务、库与合成凭据按夹具生命周期清理。
- 前端定向 PlanReadClient 回归 9 项；最终全量 `155` 文件、`1847` 项通过，typecheck 与生产 build `337` 模块通过。首轮失败不计入通过结果。

## 兼容、回滚与遗留

修正仅改变 Plan 读取客户端调用原生 fetch 的 receiver；不改 Migration、冻结 API、权限、License、依赖或旧数据。回滚可撤此客户端修正和一次性验证夹具，但会重新暴露实际浏览器详情读取失败。合成 License/账户只证明功能链，不等于正式公钥、目标服务账户、离线安装、客户 UAT 或多平台发行。PlanVersion、WBS、Output 和完整 Pilot 仍待后续 WBS。
