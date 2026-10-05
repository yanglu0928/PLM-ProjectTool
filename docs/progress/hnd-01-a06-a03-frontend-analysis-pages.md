# HND-01-A06-A03：Handover Analysis 页面与按需原文定位

日期：2026-10-05。结论：`HND_01_A06_A03_FRONTEND_ANALYSIS_PASS`。下一项：`HND-01-A06-A04` Action LIST/GET 严格客户端与只读待办页。

## 实施结果

新增项目交接分析列表、详情路由及项目详情导航。列表只显示分析目的、状态、正式版本引用和更新时间；分页 cursor 只保存在当前组件内存。详情逐层读取 Analysis、Version 摘要、选定 Version 固定输入和 Item，不在浏览器拼接后端内部事实。

每个 Item 以问题卡片展示类型、状态、严重性、优先级、陈述、影响和建议。`NEED_CONFIRM` 明确展示确认问题、服务器选项，以及 `name/required/format/example` 四部分人工维护提示，并声明示例不是客户事实。固定 Document 与 AI Task 只导航到各自 Owner 页面；没有写表单、接受建议或自动确认动作。

EvidenceId 初始仅显示为受控引用。用户点击“定位原文”后才调用既有 Evidence Viewer，重新验证当前权限、固定 DocumentVersion、指纹和 locator；成功后显示位置、短提示和受权固定版本入口。新定位开始即清除旧位置，失败不保留陈旧结果；切换项目/Analysis/Version、迟到响应或撤权均由代次与当前 Session 检查隔离。

## 客观验证

- 新增页面 8 项，连同项目详情导航定向共 26 项通过；覆盖无身份/改密关闭、最小列表、翻页/刷新、后续拒绝清空、跨项目迟到响应、Version/Item 分层读取、结构化维护提示、按需定位及定位失败清旧。
- 前端全量 72 个文件、1296 项通过；TypeScript typecheck 和 Vite production build（156 modules）通过。
- Vite 报告主 JS `524.49 kB` 超过默认 500 kB 提示；构建成功且不是功能阻断。当前路由仍为静态导入，后续发行性能任务应评估按路由动态拆包并以真实加载测量验收，不在本任务跨范围改造全局路由。

## 兼容、回滚与未关闭项

纯前端页面与路由增量；无 Schema、Migration、后端 API、依赖、配置、Secret、外部网络或客户数据外发变化。撤页面路由和项目导航即可回滚，服务器历史不变。

Action只读页、Analysis/Action写UI、Action写HTTP、真实浏览器/PostgreSQL组合、路由拆包性能、正式key/信任、Gate 3、UAT与发行仍按总状态跟踪。
