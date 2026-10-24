# SOL-06-A12-P02：结构化专项受锁修订 Repository

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVISION_REPOSITORY_PG_PASS`；仅表示内部持久化边界通过，不代表修订 Service、HTTP、Windows 装配或用户界面已可用。TraceLink：冻结 `SOL_SPEC_REVISE` → SOL-06-A12-P01 修订语义 → 本项受锁 Repository。
- 编码前检查：复用 0164 不可变专项根、载荷与来源引用表，不新增 Schema；修订路径仍由后续 Service 负责 Session/CSRF、License、项目角色、幂等回执和 Audit。本项只解决“按项目锁定期望前驱并原子创建下一版本”一个问题。
- 实现：新增 `StructuredSpecRevisionBase`，在同一事务中先按 `ProjectId + spec_id` 隐藏跨项目对象，再取得系列 advisory transaction lock，并锁读请求版本和系列最新版本。返回固定系列、类型、请求/最新版本号与当前状态；结构、版本或状态异常均失败关闭。
- 替代版本：`revise` 只接受路径版本仍为最新且状态为 `DRAFT`、`RETURNED` 或 `APPROVED` 的 base；重新证明后的完整快照必须绑定同项目、同系列、同类型和路径前驱。持久化复用既有 CREATE 的不可变根/载荷/来源引用写入与最新版本复核，结果必须为 `version_no + 1` 且正确指向前驱。
- 并发与隔离：Windows 11 可弃 PostgreSQL 18.6 上，两个线程同时以 v2 为前驱修订，advisory lock 串行化后仅一个生成完整 v3，另一个看到最新版本变化并返回 `VERSION_CONFLICT`；陈旧 v1 可读取其固定 base 但不能作为当前替代前驱，跨项目查询返回空。
- 验证：定向 `13 passed / 11 subtests`；完整后端 `3651 passed / 3 skipped / 5753 subtests`；真实 PostgreSQL 验收检查 v1→v2→v3 根、载荷、需求和章节引用均各三份且并发无重复；开发 wheel 1399 条目，SHA-256 `3b7915143ad9cf243dd99f7a8723489b6695e26d59be934e0f3e630a94971406`，包含新增运行文件。
- 兼容性/升级：无 Migration、冻结 API 字段、License 权益、角色或依赖变化；现有 0164 数据无需升级。只新增尚未公开装配的内部读取/写入方法。
- 回滚：可撤回 `StructuredSpecRevisionBase` 和两个 Repository 方法；已写不可变专项版本不得删除或改写。当前真实验收数据仅存在于验证器创建并清理的可弃数据库。
- 已知边界：独立修订策略、Service、幂等收据、Audit、HTTP、Windows 平台装配、前端和 Edge 尚未实现；正式服务账户信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行仍未通过。本项未外发客户数据。
- Next：`SOL-06-A12-P03` 实现独立修订 Service，完成当前授权重核、来源重证、首次结果回执、Audit、重放与事务回滚；仍不开放 HTTP。
