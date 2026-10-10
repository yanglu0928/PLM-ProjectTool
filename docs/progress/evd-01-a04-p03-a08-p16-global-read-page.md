# EVD-01-A04-P03-A08-P16：GLOBAL Evidence 受权只读页面

日期：2026-10-01；Phase 2 Platform Core；结果：`FRONTEND_GLOBAL_READ_COMPONENT_PASS / BROWSER_AND_WRITE_OPEN`。

编码前检查：输入冻结 GLOBAL Evidence List/Get/Viewer、P15 当前强 ETag 客户端、P14 历史回查客户端。全局页面需要先提供受权固定来源浏览，人工写入与原操作号恢复是独立 WBS；本项只改前端只读页面、路由/导航和测试。无实体、后端 API、Schema、角色或依赖变化。只允许当前 DeploymentAdmin 会话；Viewer 与列表固定 Document/Version 必须一致，再 GET 当前 Evidence 并比对来源，才显示相对受权内容 URL。

新增 `/admin/evidence` 列表/分页和“定位固定原文”。无身份/普通身份不发送 Evidence 请求；提示与列表不包含物理路径。刷新/卸载丢弃旧选择和异步结果；来源漂移不展示下载入口。新增页面 5 项和 GLOBAL 列表路径 1 项，前端全量 1,057 项、typecheck/build PASS。首次全量回归发现 AppShell 导航数量断言仍为 6，按新增导航更新为 7 后重跑全绿；未更改生产权限策略。

兼容：前端路由和导航增量，不改 API/Schema；无迁移。回滚移除新页面/导航，后端既有 Evidence/收据保留。页面目前只读，不提供 GLOBAL 人工资格写入或原操作号恢复；真实浏览器、目标账户/HTTPS、Server2025/Debian及 Gate3 未验。
