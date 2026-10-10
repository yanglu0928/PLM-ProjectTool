# SOL-04-A18：Section 只读列表/详情页

日期：2026-10-09。结果：`SOL_04_A18_SECTION_READ_PAGES_PASS`；前端合同通过，真实浏览器/PG 留待 A21。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A18。
- 输入基线：Gate 2 API-04、A17 Section 安全读客户端、A15 Windows 后端组合；前置满足。
- 模块/实体/API/权限：Solution 前端两个只读页面、Router 与 Outline 详情入口；Section/Outline 身份，冻结 GET/LIST 无变。当前项目成员可读，前端仅作初步门控，服务端最终复验。
- 验收：项目成员列表/详情、分页、空/错误、跨项目不发请求、父目录导航与身份/批准状态免责声明；页面合同、前端全量/typecheck/build。
- 风险：从 Outline 进入却误以为列表只含该目录章节；接口当前不提供父目录筛选，故页面明确列出全项目并保留每项所属目录链接。

## 实施与验证

新增 `ProjectSectionListView`/`ProjectSectionDetailView` 及项目级路由；Outline 详情链接注明“整个项目的方案章节”。列表按 SectionId 检查跨页重复/逆序，错误清空可见页，路由切换使用代次屏障避免旧请求污染。详情只展示身份、状态、批准版引用与强 ETag；页面声明不展示正文、评审决定或客户签署，不把身份当交付。客户端对完整投影、Session/License/项目权限仍独立验证，前端门控不是后端授权替代。

页面与既有 Outline 定向合同 `7 passed`；前端全量 `115 files, 1671 passed`；`pnpm --dir apps/frontend build` 包含 typecheck/build，退出 0。真实浏览器/PG 与正式目标账户未运行，不能标 UI 端到端通过。构建既有大块提示未改变本项验收结论。

兼容/升级/回滚：无 Schema/Migration、依赖、冻结 API 或写权限变化；撤下新路由/入口可回滚，Section 历史保留。下一项 `SOL-04-A19` 创建传输/客户端，再 A20 创建页、A21 Win11 浏览器/PG。TraceLink：Gate 2/API-04 → A16/A17 → A18 → A19。
