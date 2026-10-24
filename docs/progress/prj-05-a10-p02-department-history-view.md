# PRJ-05-A10-P02：部门历史只读页面

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端合同，非真实浏览器/PG）。输入为 PRJ-05-A10-P01、冻结 Department GET 与 DEC-20260929-451。
- Changed：项目详情增加“查看项目部门历史”入口，独立页面展示有效/停用部门、编号、名称、创建时间；固定50条刷新与续页。无身份/强制改密不请求；失败、重复跨页 ID、项目切换或卸载清除/丢弃旧数据与迟到结果。页面不提供写操作，也不以 Session 摘要代替服务器授权。
- Files：Project Department 页面/测试、路由、Project 详情入口、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚撤页面/路由/入口，P01只读客户端保留。
- Tests：前端563/563、typecheck、build PASS；真实浏览器/PG未运行。
- Known Issues/Next：跨页数据不保证同一时刻快照；正式信任、Server 2025/Debian、性能/质量、Gate 3/可用包未验。下一项 PRJ-05-A10-P03 Windows 11 实际浏览器/隔离 PostgreSQL 验收。
