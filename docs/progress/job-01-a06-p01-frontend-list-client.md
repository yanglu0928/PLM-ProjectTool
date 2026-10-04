# JOB-01-A06-P01：前端 Job 列表只读客户端

2026-10-02 / Phase 2 / INTERNAL_PASS（客户端合同）。输入基线：冻结 `/api/v1`、`JOB-01-A05-P05` 已验证的 Windows 显式 Job 列表；Gate 2 已通过。单问题：前端安全读取项目或 DeploymentAdmin Job 列表，不接页面或写操作。

编码前检查：前置后端列表、当前 Owner 授权和独立游标已具备；仅涉及前端 Jobs API，Job 元数据投影，不改实体/Schema/后端路由、角色或 License。项目入口仅传规范 ProjectId；管理员入口独立且只允许 GLOBAL/DEPLOYMENT 筛选。GET 同源 Cookie、no-store、无重试，原样传递服务端不透明游标；服务器仍承担当前会话/项目/Owner 授权与游标验签。客户端只保留允许展示字段，拒绝跨 Scope/Project、畸形状态/版本/结果、重复 Job、错误分页和不匹配的安全错误合同，不显示服务器异常内容。

Files：`apps/frontend/src/modules/jobs/api/jobListClient.ts` 及同目录测试。Migration/API/依赖：无。兼容性：仅未接线的前端客户端增量；现有页面/产物行为不变。升级/回滚：无数据迁移，撤新客户端与测试即可，旧 Job 后端和历史记录保持。

验证：定向 26/26、前端全量 1,091/1,091、typecheck 和 Vite build PASS；构建资产仍为原有 index JS/CSS（客户端尚未由页面引用）。未运行真实浏览器、后端网络/数据库端到端或三平台正式账户测试，不以本项推定 Gate 3。风险：尚无 UI 暴露，正式 License/游标密钥、法律审阅、Server2025/Debian 和 UAT 保持开放。

Next：`JOB-01-A06-P02` 只读 Job 列表页面与安全导航，先核对当前路由/会话与项目权限展示；不借本项启动取消/重试前端写入口。
