# PLAN-01-A04-P05-A02：Plan 项目入口与当前身份页面

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A04_P05_A02_FRONTEND_PAGES_PASS`。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A04-P05-A02`|
|输入基线|冻结 PLAN_CREATE/GET/LIST、A04-P04 Windows HTTP/PG、A04-P05-A01 安全客户端及现有项目导航/Session UI模式|
|前置任务|客户端严格 DTO、排序与原幂等 Key 合同已通过；实际页面和浏览器尚无|
|涉及模块/实体|Plan 列表/创建/详情 Vue 页面、项目详情入口、前端路由；不改后端数据模型|
|涉及 API|消费冻结 Plan 身份 API，无新路径/字段；UI 不把身份写作版本、WBS、正式确认或交付|
|涉及权限|项目成员当前读取；ProjectManager/ImplementationMember 仅显示创建入口，服务器继续做最终授权；切项目/撤权/失败清除旧数据|
|验收|项目导航、空列表/分页、严格时间-ID降序续页、详情、不可确定写保留原Key/二次确认、跨项目及迟到响应清屏、定向/全量/typecheck/build|
|风险|将旧项目数据带到新项目、超时后新Key重复创建、误称Plan身份为实施WBS、UI权限代替服务端权限|

本项只安装身份页面；`PLAN-01-A04-P05-A03` 才做 Edge 真实浏览器/PG 验收。正式版本/WBS/输出仍须独立开发。

## Changed / Files / Migration / API

- Changed：项目详情增加“查看实施计划”入口；增加列表/创建/详情三个项目内页面，列表可刷新和签名游标加载更多、跨页严格按创建时间及ID倒序并拒重复；路由切项目清空旧页且晚到响应不能复现旧内容；详情仅显示当前身份。创建页只在当前可写角色显示表单，提交前将原项目/actor/名称/Key保存在会话存储；结果未知保留原 Key，须用户核对并确认后按原值重试，损坏或无法保存则停止写入。
- Files：`apps/frontend/src/app/router.ts`、`modules/project/views/ProjectDetailView.vue`、Plan ReadClient排序辅助及 `modules/plan/views/` 三个页面/两份测试；选择见 `DEC-20261019-1230`。
- Migration：无。API：只消费现有冻结 Plan 身份合同，不新增后端路径/字段/角色/许可机制。
- Upgrade/Rollback：重建前端资源即可出现页面；可撤入口和路由，已有 Plan/收据/Audit 历史保留。

## Tests / Result / Known Issues / Next

- 定向 Plan 页面/ReadClient 3文件11项、typecheck通过；前端全量155文件1846项、typecheck与生产构建337模块通过，生成独立 Plan 页面 chunk。主chunk 805.75kB 的现有超过500kB提示仍在。
- 本项仍是前端组件/合同验收，不代表真实 Windows 11 Edge/PG页面已经通过；A03 需实机交互。正式服务账户密钥、License公钥/可信时间/HTTPS、PlanVersion/WBS/Output及Gate3/Pilot/Release仍未通过。

Next：`PLAN-01-A04-P05-A03` Windows 11 Edge + 生产 Vue + FastAPI/Uvicorn + 可弃 PostgreSQL 实际页面创建/读取/翻页/隔离与唯一审计验收。
