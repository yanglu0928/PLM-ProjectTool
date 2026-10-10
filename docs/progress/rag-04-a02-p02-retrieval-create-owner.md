# RAG-04-A02-P02：受权异步 Retrieval 创建 Owner

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_RETRIEVAL_CREATE_OWNER_PASS`

## Changed

新增只支持无外发 `fts.project.v1 + none.v1` 的内部异步创建 Owner。命令先规范化 query 和固定 allowlist metadata filter，再在当前 Session/CSRF、License、Project 成员权限、ACTIVE Index/Model/Chunk 事实及幂等范围全部通过后，使用专用 AES-256-GCM 端口加密 query。

Job 只保存 `retrieval_run_id`；Run 只保存指纹和安全引用。Job、Run、密文 QueryContent、Project Audit 和通用幂等收据在同一 PostgreSQL 事务中提交。同 Key 重放仍重验当前权限与 License，不生成新密文；撤权后重放拒绝。query 输入缓冲无论成功失败都归零。

## Files

- `apps/backend/src/plm_assistant/modules/rag/application/create_retrieval.py`
- `apps/backend/src/plm_assistant/modules/rag/application/retrieval_query_crypto.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/retrieval_create_repository.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/retrieval_query_crypto.py`
- `apps/backend/src/plm_assistant/modules/project/application/authorization.py`
- `apps/backend/tests/unit/test_rag_retrieval_create.py`
- `apps/backend/tests/unit/test_rag_retrieval_query_crypto.py`
- `apps/backend/tests/unit/test_project_authorization.py`
- `validation/rag-04-a02-p02-retrieval-create/`

## Migration / API / Compatibility

- Migration：无；复用 Schema0088。
- API：无；冻结 POST 路由尚未挂载。
- 权限：`RAG_RETRIEVAL_CREATE` 允许 ProjectManager、ImplementationMember、CustomerManager，并按写操作锁定当前 Project/Member/Department。
- 依赖：无新增；复用已锁定 `cryptography==50.0.1`。
- 回滚：停止新 Owner 调用即可关闭新建；已产生的 Run/Job/Audit/收据和密文历史保留并向前修复，不回退明文。

## Tests

- 定向单元：Query Cipher 4、Create Owner 5、Project Authorization 7，共16项 PASS。
- Windows 11 / PostgreSQL 18.6：真实 Session/CSRF、Project 成员、合成 License 与合成 ACTIVE Index 组合 PASS；Audit 故障五类状态全回滚，幂等重放、撤权后重放、错 CSRF、License 关闭及错 Index 负例 PASS。
- 明文检查：Query 未出现于 Job/Audit，密文不等于 UTF-8 明文，专用密钥可以按 AAD 完整回读。
- 后端全量：2467 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 中 RAG 隔离回归：95 项 PASS；SHA-256 `14a6a8ce6b7293e63acbb7f40a15bbb513ba938a8649ea978b138b9420a0fe12`。

## Result / Known Issues / Next

结果：`PASS`。本项只证明无外发 FTS 创建边界；没有执行候选召回、Worker claim、Context 构建或公开 HTTP。复用的 ACTIVE Index 是合成机制夹具，不是正式业务质量证据。正式内容密钥供给、独立质量集、性能、Windows Server 2025、Debian 13、Gate 3、UAT 和发行包未通过。

下一项：`RAG-04-A03-P01` 执行链前置核查，锁定专用 Job claim、当前授权再验、QueryContent 受控解密、参数化 FTS 与候选快照的原子边界。
