# SOL-06-A12-P05：结构化专项修订 Windows 装配与真实 HTTP/PG

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVISION_WINDOWS_HTTP_PG_PASS`；仅证明 Windows 11 显式读写组合，正式信任和其他目标平台仍未通过。TraceLink：冻结 `SOL_SPEC_REVISE` → A12-P01～P04 → 本项。
- 编码前检查：复用现有 Windows Auth、License、Audit、Document/Parse、Requirement、Section、Evidence 和 PostgreSQL 运行时；本项只把已验证的 revise Router 装入 `--platform-write`。默认应用、登录专用和只读组合均不装配该写入口。
- 装配：新增 `create_windows_structured_spec_revise_router`，所有 runtime/session/origin/license/audit/document/download/parse 依赖必须显式存在；任一缺失或构造异常均转换为启动失败，不提供测试回退。生产组合仅在 `include_secret_write` 下创建并注入该 Router。
- 真实链：Windows 11 可弃 PostgreSQL 18.6 上，通过真实 Session、项目角色、当前 Requirement/Section/Document/Evidence 来源和 ASGI 请求完成 v1→v2→v3。ProjectManager 创建 v2、ImplementationMember 创建 v3；同 Key 重放保持首次结果和新 TraceId，同 Key 改正文、陈旧前驱、跨项目、错误 CSRF、查询参数及 Artifact 引用均按合同拒绝。
- 数据证据：目标 series 根/载荷均为 3 个完整版本；独立修订收据和 `SOL_STRUCTURED_SPEC_REVISED` Audit 各 2 条。创建专用但未注入 revise Router 的应用对 revise 路径返回 404；缺 Document 来源的 Windows 修订工厂拒绝启动。
- 验证：Windows/生产组合相关定向 `53 passed / 81 subtests`；完整后端 `3661 passed / 3 skipped / 5791 subtests`；真实 HTTP/PG 验收及上游创建链通过；开发 wheel 1401 条目，SHA-256 `a49a2c9a17c7bf5e473d01fa0a712fa2a5e7f00032aa9f30efcb548a881c0183`。
- 兼容性/升级：无 Migration、冻结 API、License 权益、角色、Secret、依赖或旧数据变化；已有 Windows 写模式在具备既有信任与来源依赖时新增冻结 revise 路径，无数据升级。
- 回滚：撤生产组合和 Windows 工厂接线即可关闭新入口；历史版本、收据和 Audit 必须保留。本项使用合成账户/License 和可弃数据库，未外发客户数据。
- 已知边界：合成信任不代表正式服务账户、公钥、License、Vault/ACL/CA；前端和 Edge 尚未完成，OutputArtifact、专项验证/送审、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行仍未通过。
- Next：`SOL-06-A12-P06` 新增专项修订前端安全客户端和页面，从固定详情显式进入，保留原输入/Key 的未知结果恢复规则。
