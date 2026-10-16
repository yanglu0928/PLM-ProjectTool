# SOL-06-A11-P03：结构化专项列表签名游标

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：冻结 `SOL_SPEC_LIST` → A11-P01 全版本分页语义 → A11-P02 内部 keyset → 本项。当前 Phase 2。
- 编码前检查：内部 Repository 已按 `before_spec_id` 验证 UUID 降序分页。本项仅增加 API 边界的游标编解码器和负例测试；不接 HTTP/Windows，不改 Schema、Service、权限或依赖。
- Changed：新增独立 `StructuredSpecListCursorCodec`，仅接受 32 字节专用 HMAC 密钥；签名载荷固定绑定版本、family、ProjectId、Session SHA-256、page_size 查询指纹和 `before_spec_id`。解码进行规范 Base64、固定字段、UUID 正规形式、恒时 MAC 及重新编码一致性校验；失败统一为 `REQUEST_MALFORMED`。
- 验证：3 项/12 子例通过，覆盖往返、篡改、错误密钥、跨 Outline family、跨 Session、跨 Project、改变 page_size、无效 key/位置与零 UUID。此项新增文件独立，P02 完成后的后端全量 `3638/3 skipped/5710 subtests` 与 wheel 证据保持有效；新增游标未重新跑全量，HTTP 接线时将合并回归。
- 兼容性/升级/回滚：无 Migration、公开 API 行为、外部依赖或旧数据变化；移除未装配 codec 即可回滚。游标未来由专项列表独立密钥来源供给，不允许复用测试常量。
- 限制：生产目标账户游标密钥来源、备份恢复、HTTP/Windows/UI/Edge 尚未完成；本项不证明正式信任或列表已对用户开放。专项修订/验证/送审、OutputArtifact、章节六维、Gate 3/Pilot/正式 Release 仍待。
- Next：`SOL-06-A11-P04` 接入默认关闭的冻结列表 GET，严格查询、统一错误/trace/no-store，并以合同测试验证分页与权限边界。
