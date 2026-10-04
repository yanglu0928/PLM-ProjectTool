# JOB-01-A06-P03：部署管理员 Job 只读列表

2026-10-02 / Phase 2 / INTERNAL_PASS（前端合同）。输入：Gate 2 冻结 `JOB_ADMIN_LIST`、`JOB-01-A05-P05` Windows 显式后端列表、`JOB-01-A06-P01` 安全客户端。编码前检查：仅 Admin Job 前端列表、导航与相应测试；不改实体、Schema、后端 API、权限、License 或依赖。只有当前 Session 的 DeploymentAdmin 可发起请求；服务端每页继续复核身份/Owner，Admin 范围不包含 PROJECT Job。

实现：新增 `/admin/jobs` 页面、主导航，全部/GLOBAL/DEPLOYMENT 筛选；请求代次隔离切换 Scope 前的旧响应，分页去重、失败或撤权清除旧列表；仅显示安全元数据，不开放取消、重试或下载。原项目 Job 页面保持不变。

Files：`apps/frontend/src/modules/jobs/views/AdminJobListView.vue` 及测试、`apps/frontend/src/app/router.ts`、`apps/frontend/src/app/AppShell.vue` 与导航回归测试。Migration/API/依赖：无。兼容性：前端路由/导航增量，后端需显式 Windows platform 模式及独立 Job 游标密钥；普通默认后端仍关闭。升级：重新构建前端，无数据迁移。回滚撤新页面/路由/导航，不影响 Job 历史。

验收：管理员/非管理员、Scope 切换旧请求、翻页拒绝清旧数据、PROJECT Job 误投影拒绝定向5/5；全量前端1101/1101、typecheck/build PASS。首次全量因新增导航使旧计数断言失败，更新对应断言后通过；首次连跑构建返回 Windows 进程异常退出码，分开重跑构建退出0。未执行真实浏览器/正式账户/三平台验收，不将其记为 Gate 3 PASS。

Next：`JOB-01-A06-P04` Job 详情前端安全客户端，先核冻结投影、强 ETag 和 Project/Admin 区分；页面另立分项。正式 License 信任、法律、质量/UAT 与发行仍开放。
