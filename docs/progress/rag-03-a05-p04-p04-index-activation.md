# RAG-03-A05-P04-P04：当前事实重验与原子 Index 激活

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_EMBEDDING_INDEX_ACTIVATION_OWNER_PASS`

## Changed

- 新增 `RAGEmbeddingIndexActivationService` 与 PostgreSQL 仓储。调用要求 Session/CSRF、当前 ProjectManager/DeploymentAdmin 和 License 重验，且历史幂等重放也不跳过当前权限。
- 仓储按 Scope/Project/purpose 有序锁定所有 Index，选取最新 QualityResult，要求它为 PASSED；同事务重验 Embedding Model AVAILABLE/维度、Build SUCCEEDED/技术 PASSED、来源 Chunk ACTIVE/指纹/Scope及所有构建授权未撤销且未过期。
- 切换时先将同 Scope/Project/purpose 旧 ACTIVE 原子改为 RETIRED/版本+1，再将新 READY/v2 改为 ACTIVE/v3，并写入精确绑定 QualityResult的 Audit、ActivationResult 和幂等回执。Schema0087 deferred validator 仍是最终提交防线。
- 调用方不能指定 QualityResult、旧 ACTIVE 或新版本，避免择优历史 PASS、退役错误 Index 或绕过当前事实。

## Compatibility / rollback

- 内部应用/仓储增量，无新 Schema、公开 `/api/v1`、依赖或 Provider 协议变化。
- 可停止组合激活 Owner 以禁止后续切换；已激活/退役历史不逆向改写，依 Schema0087 和 ActivationResult 向前修复。
- 本项的 ACTIVE 只存在于用后即删的隔离合成库，不是项目正式业务质量或上线状态。

## Tests

- Windows 11 / PostgreSQL 18.6：从技术 READY/v2 和服务端登记的合成 90%/98% PASS 出发，真实完成 Session/CSRF、ProjectManager、License、Quality/Model/来源/构建授权重验。
- 错误 CSRF、License 失效、Audit 故障全部在激活前失败关闭；Audit 故障后 Index 仍 READY/v2、ActivationResult 为 0。
- 成功路径同事务产生 ACTIVE/v3、一条 Audit、一条 ActivationResult 和一条 completed receipt；同键重放返回原结果，新键对已 ACTIVE Index 失败，角色撤销后原键重放也拒绝。
- 无旧 ACTIVE 的首次激活完成 PostgreSQL 组合验证；旧 ACTIVE 退役的应用版本投影通过单元测试，其数据库原子绑定已由 P02 Schema0087 证明。本项不将两者合并冒充为双代完整业务演练。
- RAG 定向 81 项通过；后端全量 2453 项通过、3 项条件跳过。
- 洁净 wheel 安装后 RAG 81 项通过；SHA-256 `cf47841ad85b2808901c73aef54659efe2cd318adfddbc8f079fe5ea01c9b475`。
- 零真实 Provider I/O、零客户数据外发、零 Secret 入库。

## Known issues / Next

`RAG-03-A05-P04` 机制实现完成，但仓库仍没有未参与调优的新独立业务质量证据，正式 ACTIVE、Gate 3、UAT 和发行包不因合成验证而通过。下一项进入 `RAG-04-A01` RetrievalRun/ContextBundle 编码前检查。
