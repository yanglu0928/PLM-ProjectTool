# SOL-06-A16-P07：Reviewer Inbox 前端

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_INBOX_FRONTEND_PASS`；前端合同与构建通过，Windows 11 Edge/真实 PG 页面闭环留 P08。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P07`|
|输入基线|冻结 REVIEW_LIST、CR-RVW-004、A16-P02～P06，现有 Project 详情/Review 已知 ID 路由|
|前置任务|P06 Windows 显式组合、真实 ASGI/PG 与专用游标 key 已通过；可从项目页进入列表|
|涉及模块|Review 列表客户端/页面、前端路由、项目详情入口和已知 Review 返回链接|
|涉及 API/数据|只调用 `GET /api/v1/projects/{project_id}/reviews`，不提交决定或创建事实|
|权限|服务端逐页鉴权；前端只按当前 Session 项目列表展示入口，失权/切项目清除旧结果|
|验收|无需手填 UUID、`my_pending/all` 分离、隐藏空页自动续取、安全响应校验、错误清屏、全量/typecheck/build|
|风险|把可见历史当待办、隐藏空页误判结束、跨项目/会话残留、游标循环或后页失败显示半旧列表|

## 实施与验证

- 项目详情加入“我的评审待办与历史”，新路由 `/projects/:projectId/reviews` 默认显示服务端 `my_pending`；也可切换 `all` 历史。每项从列表精确跳到原有 Review 详情，详情可返回列表。状态说明明确评审不是客户确认或 UAT。
- 客户端严格校验项目、页大小、专用 `r1.` 游标、响应 Trace/`no-store`、字段白名单、Subject/状态/当前用户 Assignment、终态 `active_round=null`，只识别约定的 401/403/404。服务器隐藏整页时允许 `items=[]/has_more=true`；页面自动继续，单次操作最多 20 页，后续用继续加载按钮。游标循环、重复对象、任一页错误则清除本次结果。
- 监听 Session 修订和项目/路由变化，立即清除旧待办及游标；刷新重新从第一页获取。页面不把本地缓存/历史 Assignment 当授权或待办来源。
- 定向 4 文件 `29 passed`，覆盖客户端合同、自动空页续取、决定后待办消失但历史可查、后页故障、会话撤销和跨项目切换；前端全量 `151 files / 1831 passed`，Vue/TypeScript typecheck 与 Vite production build 通过，新列表 chunk 入包。既有主 chunk 超 500 kB 提示仍在。

## 兼容、升级与未完成项

- 仅前端静态资源、路由和入口变化，无 Migration、后端 API/权限/License/密钥或旧数据变更。重新构建静态资源即可升级；可撤前端入口/页面，服务器 Review 历史必须保留。
- P08 要在 Windows 11 Edge 与真实 ASGI/PG 验证从项目发现待办、作决定后刷新消失、历史仍在以及跨项目清屏。当前测试账户和 License 为合成环境，正式信任、Gate 3/Pilot/发行未通过。

Next：`SOL-06-A16-P08` Windows 11 Edge/PG 实际页面闭环验收。
