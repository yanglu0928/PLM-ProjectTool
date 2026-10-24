# SOL-06-A10-P03：Windows 专项详情 GET 装配

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：冻结 SOL_SPEC_GET → A10-P01 内部读取 → A10-P02 HTTP 合同 → 本项。
- 编码前检查：Phase 2；既有 Windows 显式平台只读/读写模式、Session、Project Authorization、License Guard、P01/P02 均就绪。涉及运行组合与 SOL-06 GET，不改业务实体/Schema/冻结路径或写策略。缺运行依赖时拒装，默认应用不挂载。
- Changed：Windows 显式只读与读写平台模式装配受权专项详情路由；复用正式设计的当前账户会话、Project/License 组合，不引入写权限、文档正文访问或新密钥。复用旧创建夹具可选回调，验收真实创建后的详情。
- 验证：Windows 11 可弃 PostgreSQL 18.6/ASGI 的真实合成账户、Session/License/项目授权和来源链：两名项目成员创建后读回固定草案，GET 与首次数据一致；默认关闭、跨项目 404、缺 Session 401、额外查询 400、缺装配依赖拒绝。原 SOL-06 CREATE 验收同步通过。后端全量 3636 通过/3 跳过/5706 子例；开发 wheel 包含 Windows 组合和运行入口（1396 条目）通过。
- 兼容性/升级/回滚：无 Migration、破坏性 API、依赖或旧历史变更；可关闭显式平台模式/撤回装配，已写历史保留。合成 License/测试账户不证明正式发行信任。
- 限制：前端专项详情仍缺，OutputArtifact Owner、Review/章节六维、Gate 3/Pilot/正式三平台发行未完成；Server 2025/Debian 13 未实测。
- Next：`SOL-06-A10-P04` 前端专项详情读取客户端与页面。
