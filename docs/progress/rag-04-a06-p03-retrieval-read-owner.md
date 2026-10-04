# RAG-04-A06-P03：Retrieval 当前受权只读 Owner

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P03_RETRIEVAL_READ_OWNER_PASS`

## Changed

新增 Run、Result、Context 的独立应用读取服务和 PostgreSQL 仓储。每次读取在同一事务中依次重验当前 License、真实 Session、Project/Department/Membership，并以共享锁固定 Run 与来源文档状态。创建者可读自身 Run；ProjectManager、CustomerManager 作为监督角色可读；普通非创建者统一按资源不存在失败关闭。

Run 仅返回状态、Index/Policy、质量、Job、Trace 和时间等安全元数据；不返回 query 原文、密文、metadata filter 或 query fingerprint。Result 只返回受权 Candidate/DocumentVersion/ParseResult locator、整数分数分解及最长8192字符 snippet；Context 只返回固定 Bundle、来源、截取范围、顺序、token和同样有界的最小正文。两类正文投影均逐次复验当前 ACTIVE Document/Chunk 与 AVAILABLE Version，不返回向量、Golden标签、人工答案或其他项目存在性。

## Files

- `apps/backend/src/plm_assistant/modules/rag/application/retrieval_read.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/retrieval_read_repository.py`
- `apps/backend/src/plm_assistant/modules/project/application/authorization.py`
- `apps/backend/tests/unit/test_rag_retrieval_read.py`
- `apps/backend/tests/unit/test_project_authorization.py`
- `validation/rag-04-a06-p03-retrieval-read-owner/README.md`
- `validation/rag-04-a06-p03-retrieval-read-owner/verify.py`

## Authorization / Compatibility / Rollback

- `RAG_RETRIEVAL_GET`、`RAG_RETRIEVAL_RESULT_GET`、`RAG_CONTEXT_GET` 进入 Project 当前权限矩阵并锁定当前授权事实；服务层再按创建者或监督角色收窄对象级可见性。
- 按CR-RAG-004/A06-P01安全最小化，冻结候选DTO中曾列示的query fingerprint不进入公开投影；其仍保留在数据库内部供完整性和幂等校验，避免低熵查询被离线猜测。P04 HTTP以此修订后的最小投影为准，原冻结提交不追写。
- 无Migration、公开HTTP挂载、依赖、网络或数据外发变化；可撤读取Owner与后续Router回滚，Run/结果历史不改写。

## Tests

- 应用/权限定向12项PASS；RAG定向135项PASS。
- Windows 11 / PostgreSQL 18.6：真实成功Run下创建者、ProjectManager读取Run/Result/Context；普通非创建者和错误Project隐藏；成员撤权拒绝；Document限制后正文投影失败关闭，恢复后可读，全部PASS。
- 后端全量：2508项PASS，3项既有环境条件跳过。
- 开发wheel隔离导入：RAG 135项、Migration Contract 4项PASS。wheel SHA-256：`e2d2dbb8419b7cfae18d13658bfbe493a19ea18140ebdfb107638d3dc26988b9`。

## Result / Known Issues / Next

结果：`PASS`。三类读取已形成当前授权、项目隔离、最小正文和失败关闭边界，可供冻结HTTP组合复用。

已知问题：尚未挂载Create/Get/Result/Context HTTP；取消Owner、生产Worker组合、前端、真实浏览器闭环、正式质量/性能、Windows Server 2025、Debian 13、Gate 3、UAT和发行包仍待。

下一项：`RAG-04-A06-P04`，实现严格 Create/Get/Result/Context HTTP 合同与opt-in Router。
