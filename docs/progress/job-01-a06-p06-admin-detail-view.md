# JOB-01-A06-P06：部署管理员 Job 详情只读页面

2026-10-02 / Phase 2 / INTERNAL_PASS（前端合同）。输入：Gate 2 冻结 `JOB_ADMIN_GET`、`JOB-01-A04-P04` 显式后端、`JOB-01-A06-P04` 安全详情客户端与 P03 Admin 列表。编码前检查：前置已满足；只改 Jobs 前端页面/路由/列表导航，不改实体、Schema、后端 API、角色、License 或依赖。DeploymentAdmin 客户端先检查当前 Session；服务端再逐次核当前身份、License 和原 Owner，拒 PROJECT Job。

实现 `/admin/jobs/{job_id}`，从 Admin 列表任务号进入；页面只显示安全状态、版本、时间、逻辑结果引用，不链接物理内容，不开放取消或重试。刷新先清旧详情；JobId 路由变化以请求代次丢弃晚到响应；撤权/来源不匹配清除显示。结果引用不作为下载授权。

Files：`apps/frontend/src/modules/jobs/views/AdminJobDetailView.vue` 及测试、`apps/frontend/src/modules/jobs/views/AdminJobListView.vue` 与测试、`apps/frontend/src/app/router.ts`。Migration/API/依赖：无。兼容性：前端路由/导航增量；后端默认模式仍关闭。升级重建前端，无数据迁移；回滚撤页面/路由/链接，不动 Job 历史。

验证：定向10/10、前端全量1126/1126、typecheck/build PASS。首次测试失败因换 Job 的合成结果引用仍沿用旧 ID，修正夹具后重跑通过；不把夹具修正当产品缺陷修复。非管理员零请求、旧响应丢弃、刷新撤权清旧详情、PROJECT误投影拒绝已测。真实浏览器/正式账户、Server2025/Debian、性能、法律和Gate3未验。

Next：核 Jobs 前端只读整体与后端真实PG/HTTP联动，可在当前不含正式秘密的隔离环境验证；取消/重试前端写操作与正式发行另列任务。
