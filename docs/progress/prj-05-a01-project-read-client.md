# PRJ-05-A01 前端项目只读客户端

2026-09-28 / 0.1.0.dev0 / PASS（客户端合同；页面与真实网络待后续任务）。

编码前检查：当前 Phase 2 / WBS PRJ-05-A01；输入冻结 `API-02` 的 `PROJECT_LIST/PROJECT_GET`、既有 ProjectRead HTTP 实现与 Windows 显式平台组合、前端 Auth 同源 Cookie 客户端；Gate 2 和后端读接口前置已满足。涉及前端 Project API Adapter 和安全只读 DTO，不涉及实体、Schema、后端 API、新权限或依赖。权限始终由服务器当前 Session、License、成员身份及资源归属重新核验；DeploymentAdmin 不自动取得项目成员权。验收是单次同源无缓存 GET、严格安全投影及 ETag/ID 匹配、固定错误提示、越权/过期不泄露正文、无持久存储或自动重试、前端 test/typecheck/build 通过。风险为客户端误信登录摘要或跨项目响应；故不以 Auth 投影授予项目内容，严格验证详情 ID/ETag。回滚撤客户端及测试即可，无迁移。

L2 决定：在 Project 模块内独立实现只读客户端，不修改 Auth 客户端，也不在这一项搭建页面。列表只接受当前后端单有效成员最多一项目的 `next_cursor:null/has_more:false` 合同；今后若正式服务改为多项目分页，应先追溯增量合同并更新客户端。仅复制白名单字段，拒绝畸形 UTC-Z 时间、非强 `"vN"` ETag、非规范 UUID、错误状态/错误码组合和详情 ID/ETag 不一致；已知 401/403/404 使用固定中文消息，其余统一不可用，不显示原始服务端内容。

Changed：新增 `ProjectReadClient.list/get` 及 ProjectView/Page 安全只读投影；详情 UUID 在网络请求前校验，两个请求均仅使用相对路径、浏览器同源 Cookie、`no-store`、禁止重定向、10 秒可中止超时；不读取/持久化 Cookie、CSRF、项目授权摘要，不自动重试。此项客户端尚未被页面引用，不能当成用户已能查看项目。

Tests：新增 37 项客户端测试，前端总计 123/123、typecheck、build 最终 PASS。首次测试失败是构造时序列化断言过严，首次构建类型检查失败是测试参数化类型与 `unknown` 收窄；均已修正并重跑。未运行本项真实浏览器/PG/后端全量、覆盖率及性能；既有后端项目读实际 PG 证据不冒充本项前端端到端。无 Migration/API/权限/依赖变更。下一 PRJ-05-A02：登录后项目入口页面接线与页面级状态/错误测试；正式信任、HTTPS、Server2025/Debian、CR-AUT-008 性能 FAIL、Gate 3/可用包仍待。
