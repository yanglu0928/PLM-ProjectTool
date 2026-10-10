# DOC-04-A02：固定版本 ParseRecord 受权读取

- Changed：复用现有 Document Session、License、GLOBAL 管理员/PROJECT 成员授权，在同一事务确认受权 Document 和 AVAILABLE 固定版本后，按 `(created_at, parse_record_id)` 降序读取 ParseRecord 历史；只投影记录身份、Profile/Version、状态/Attempt、Job/不透明结果引用、脱敏错误及时间。不投影结果物理路径、Hash、正文或 traceback。
- Files：Document 内部读服务与 SQLAlchemy 仓储、单元测试、`validation/doc-04-a02-parse-read/verify.py`；Migration/公开 API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 576 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 同时间戳 keyset、Scope/Project 过滤和安全 DTO PASS；开发 wheel PASS，SHA-256 `9a6a8c548cb04b02069f194eaf8e540a6e54844179c65405b7bedd78f6749f9e`。
- Result：内部读取 PASS。尚未装配公开 HTTP、正式 Parser/OCR Worker 或结构化结果文件完整性校验；数据库 `SUCCEEDED` 仅表示元数据状态，不能作为 Evidence/RAG 已验证结果。
- Next：DOC-04-A03 冻结 `DOCUMENT_PARSE_LIST` 可选 HTTP 契约与受控游标；真实解析/精确定位留待 Phase 3。Windows Server 2025 本项未运行，Debian 13 按用户指令暂不验证。
