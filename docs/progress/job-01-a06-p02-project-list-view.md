# JOB-01-A06-P02：项目 Job 只读列表页面

2026-10-02 / Phase 2 / INTERNAL_PASS（前端合同）。前置：`JOB-01-A06-P01` 客户端及 `JOB-01-A05-P05` 后端列表已验；Gate 2 已通过。编码前检查：本项只在现有项目详情增加导航及项目任务列表页，使用当前 Session、不预先推定用户有权限；每页仍由后端核当前会话、项目与 Owner。涉及 Jobs 前端视图、Router 和 ProjectDetail 导航；Job 元数据，不改实体/Schema/API/角色/License。验收是无身份或必须改密不请求、只显示安全元数据、不出现写操作、分页/刷新/撤权清旧数据和跨项目旧响应丢弃。

Files：`apps/frontend/src/modules/jobs/views/ProjectJobListView.vue` 及测试、`apps/frontend/src/app/router.ts`、`apps/frontend/src/modules/project/views/ProjectDetailView.vue`。Migration/API/依赖：无；复用冻结的 `GET /api/v1/projects/{project_id}/jobs`，仅 Windows 显式平台后端组合可用。兼容性：新增页面与项目导航，既有路由/命令不变。升级：重新构建前端；旧前端不显示新入口。回滚：撤路由和导航，不动任务历史或后端。

验证：首次定向失败因合成必须改密账户错误包含项目权限，修正测试夹具后定向5/5、前端全量1096/1096、typecheck/build PASS。路由/页面仅 jsdom 合同，真实浏览器/正式账户/Server2025/Debian 尚未验证；不据此关闭 Gate 3 或称用户包可用。法律、正式 License/独立游标密钥供给、AI 质量/UAT 保持开放。

Next：核 `JOB-01-A06-P03` DeploymentAdmin 列表页面及项目 Job 详情是否符合当前 API/会话前置；逐项实施，不混入取消/重试写操作。
