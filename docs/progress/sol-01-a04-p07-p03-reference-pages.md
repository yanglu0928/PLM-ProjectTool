# SOL-01-A04-P07-P03：Reference 候选、详情与固定来源入口

日期：2026-10-09；结果：`REFERENCE_FRONTEND_PAGES_CONTRACT_PASS`，仅前端合同、类型检查和构建验证；真实浏览器/PG 组合待 P07-P04。

编码前检查：Phase 2 Platform Core；输入冻结 API-04、CR-SOL-008、P07-P01/P02；前置后端受权 GET/List 与前端严格客户端已通过。涉及前端 Solution 列表/详情、既有 Document 详情、Evidence Viewer 与项目路由；无 Schema、新公开 API、权限或后端依赖变更。验收为可从项目进入候选、从候选进入详情、按固定 Document 根/版本打开独立授权文档页，Evidence 经 Viewer 核验后展示定位提示与受权原文链接；异常时不显示未经核验下载。风险为历史引用并不证明当前适用/可访问，页面明确标注。

PROJECT 候选页只读、分页、允许当前授权成员查看；详情页展示固定来源与人工核对提示，不提供未实现的 GLOBAL 确认或 Eligibility 写入口。Document 详情新增 `versionId` 查询参数入口，调用既有 `getVersion` 单独授权读取后才给下载链接；失败不渲染下载。Evidence 由既有 Viewer API 按固定 EvidenceId 读取定位精度、短提示与受权内容链接，不把短提示当正文或精确高亮。修复 Reference 客户端调用浏览器原生 fetch 时误绑定 receiver 的兼容风险。

验证：新页面及固定版本定向 14 项通过；前端全量 `103 files / 1614 tests`、typecheck、Vite build 通过。构建保留既有主包超过 500 kB 警告。无数据升级；回滚可撤下新路由/项目链接和 Document 固定版本查询入口。真实浏览器、正式 License/目标账户、Server 2025、20 并发、Gate 3 和可用程序包尚未通过。Debian 13 依用户指令跳过。

TraceLink：API-04/CR-SOL-008 → P07-P01 后端定位 → P07-P02 客户端 → P07-P03 页面/定向/全量 → P07-P04 浏览器组合。
