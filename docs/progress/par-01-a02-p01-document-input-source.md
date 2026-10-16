# PAR-01-A02-P01 Document 拥有的 Parser 输入元数据 Port

- 日期/结果：2026-09-30；Phase 2 依赖前置；`WINDOWS11_INTERNAL_HTTP_PG_PASS`（仅元数据来源，不是字节快照或 Worker）。编码前检查：`CR-PAR-001`、A01 profile 合同、已提交上传 Job/Outbox、DocumentSource/Audit Port 和真实文件版本具备；决策 `DEC-20260930-498`。
- Changed/Files：在 Document Application 增加内部 `DocumentParseInputSource`/`read_input`，只有原 `CommittedParseDocumentSource` 与对应上传 Audit 证明通过后才返回私有相对 locator、固定版本 SHA-256、大小、检测 MIME；SQLAlchemy Repository 在同一调用方事务内重查 AVAILABLE FileObject/DocumentVersion 和一致元数据。DTO 拒绝绝对/临时/穿越 locator、畸形摘要/大小/MIME，不向 HTTP 暴露路径。扩展已有隔离上传组合验收。
- 偏差：首轮真实 PostgreSQL 复验失败，发现既有 `DocumentParseSourceReader` 的 SQL 查询把 `purpose_code` 错误固定为 `SOURCE_UPLOAD`，但 API 按合同保存请求用途，如 `PROJECT_RECORD`。用途不是来源类型；修复为保持 COMMITTED Intent、固定 Version/File、`source_metadata`/ordinal-0 来源和 Audit 的严格证明，移除错误用途单值要求。修复后完整重跑 exit0，未改公开字段。
- Tests：定向 Document source 7 项 PASS；Python 3.13.15 后端全量 1572 项 PASS（2 项既有符号链接环境跳过）；Windows 11 临时 PostgreSQL18.6/实际文件上传 Commit+Abort 组合 exit0，新断言固定版本 Hash/长度/PDF MIME/持久 locator 与原 Audit 证明、伪造 actor 被拒绝；随机库清理，PoC PG 恢复停止。隔离 wheel 构建 PASS。
- 兼容/升级/回滚：仅 Document 内部读 Port/验证；无 ORM/Migration、公开 `/api/v1`、权限、依赖变化，兼容 DB0049。可撤新 Port；旧用途检查本为不兼容实际上传的错误约束，回滚它会使合法 Parser Job 读取失败，须保留修复或先迁移所有合法用途（不推荐）。
- Known Issues/Next：元数据 DTO 不能作为授权令牌；尚未检查当前 Worker 租约/fencing，也未打开/复验物理文件字节或做二次来源校验。下一项 `PAR-01-A02-P02` 在短事务中绑定 Job/Outbox/Lease/Document 来源，事务外打开受控已校验快照，再短事务复核；其后真实解析/结果发布和 Evidence 精确定位仍待。正式发行信任、Server2025/Debian、Gate3/可用包未通过。
