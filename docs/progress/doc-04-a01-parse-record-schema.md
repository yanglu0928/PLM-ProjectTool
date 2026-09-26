# DOC-04-A01：ParseRecord 与受控结果引用持久基础

- 日期：2026-09-26；Phase 2 Platform Core；输入：Gate 2 冻结 DM-03/SC-01/SC-02、已有 DocumentVersion 与 Job/Outbox、`DEC-20260926-139`。
- Changed：新增 `plm.doc_parse_records`（固定 DocumentVersion/Scope/Project、`DOCUMENT_PARSE` Job、Profile/Version/Attempt、PENDING/RUNNING/终态、结果引用/Hash、时间、脱敏错误及乐观版本），以及追加保留的 `plm.doc_parse_result_refs`（受控相对 Locator、结果 Schema Version、Hash/Size）。触发器锁定版本与 Job 归属，校验 Attempt 递增、合法状态图、SUCCEEDED 对应同记录结果引用；终态不可复活，历史不可删除。修复了布尔 `retryable` 使用 `=FALSE` 时 SQL NULL 可绕过 CHECK 的风险，改为严格 `IS FALSE` 并测试。
- Files：Document ORM、Migration `20260926_0028`、迁移/元数据合同测试、`validation/doc-04-a01-parse-record-schema/verify.py`。公开 API、Parser/OCR Worker、新依赖：无；版本 `0.1.0.dev0`。升级前备份并执行 Migration；有 ParseRecord/结果历史时降级拒绝。
- Tests：Windows 11/Python 3.13 后端 572 项无失败（2 项既有符号链接环境跳过），开发 wheel PASS。隔离 PostgreSQL 18.6 已有 User/Project/DocumentVersion/Job 数据升级、空表 down/re-up、ORM drift=0、GLOBAL/PROJECT 正向、跨项目/错误 Job/跳序 Attempt/不完整成功/NULL retryable 拒绝、结果归属/不可变、终态保留与有历史降级拒绝 PASS。隔离库删除，测试服务关闭。
- Result：DOC-04-A01 持久结构与数据库约束 PASS；未运行正式 Parser/OCR，不存在真实解析结果文件的 Hash/Locator 验收。本轮手工合成的 SUCCEEDED 行只证明关系和状态形状，绝非解析成功、精确 Evidence 定位或 Gate 3 通过。
- Next：DOC-04-A02 受权 ParseRecord 列表/固定版本读取与安全 DTO；正式 Parser Worker、结果发布/物理完整性和八型精确 Locator 仍待 Phase 3。Windows Server 2025 本项未运行，Debian 13 按用户当前指令暂不验证。
