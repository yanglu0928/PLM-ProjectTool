# JOB-01-A06-P05：项目 Job 详情只读页面

2026-10-02 / Phase 2 / INTERNAL_PASS（前端合同）。输入：Gate 2 冻结 `JOB_PROJECT_GET`、`JOB-01-A04-P04` 显式后端、`JOB-01-A06-P04` 安全详情客户端。编码前检查：前置已验；仅涉及 Jobs 前端视图、项目列表导航与 Router，不改实体/Schema/API/角色/License/依赖。当前 Session 只是请求门槛，服务端仍逐次核项目、原 Owner 和 License。

实现项目 `/projects/{project_id}/jobs/{job_id}` 只读详情路由和列表 JobId 导航。无身份/必须改密不发请求；每次刷新先清旧详情，权限错误清除旧数据；ProjectId/JobId 路由变化以代次隔离晚到响应。只展示安全 Job 元数据和逻辑结果引用，不提供结果文件链接、取消或重试；结果引用不等于下载授权，强 ETag 不等于权限证明。

Files：`apps/frontend/src/modules/jobs/views/ProjectJobDetailView.vue` 与测试、`apps/frontend/src/modules/jobs/views/ProjectJobListView.vue` 与导航测试、`apps/frontend/src/app/router.ts`。Migration/API/依赖：无。兼容性：新增前端路由/导航；后端仍需显式 Windows platform 模式。升级：重建前端，无数据迁移。回滚撤新路由和链接，不动 Job 历史。

验证：定向10/10、前端全量1121/1121、typecheck/build PASS；身份、错项目/任务、路由竞争、刷新撤权、白名单展示覆盖。真实浏览器、正式账户/License、三平台及性能未执行；不据本项关闭 Gate 3。

Next：`JOB-01-A06-P06` 部署管理员 Job 详情只读页面与列表导航；写操作另立受控子任务。正式信任/法律/AI质量/UAT/发行仍开放。
