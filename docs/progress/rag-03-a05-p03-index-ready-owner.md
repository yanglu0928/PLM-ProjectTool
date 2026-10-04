# RAG-03-A05-P03：技术验证 Owner 与 READY 原子收敛

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_EMBEDDING_INDEX_READY_OWNER_PASS`

## Changed

- 新增 `RAGEmbeddingIndexValidationService`、固定技术策略与 PostgreSQL Owner。Owner 在当前单次 RAG Lease 内锁定 Build/Index，以最多 10 个现有向量作查询、Top-K 最多 5，固定 `ef_search=200`、`iterative_scan=strict_order`，分别采集受控 HNSW 与同 Scope/Project/Index exact cosine 结果。
- 技术门槛固定为 Recall 不低于 9500 basis points；该自查询冒烟只证明记录/计划/物理索引技术可用，不是业务 Golden Dataset、分类、引用或正式性能证明。
- PASS 同一事务内写不可变 Validation、完成 Job/Attempt、释放 Lease、完成 Build，并仅把 Index 从 BUILDING 推进 READY；FAILED 使用 `RAG_INDEX_TECHNICAL_VALIDATION_FAILED` 保留证据并原子关闭 Job/Build/Index。
- 新增 Schema0086：Build、Index 双向状态守卫，以及从 Job 与 Build 两侧触发的 deferred transaction validator。绕过 Owner 单独完成 Job、Build 或 Index 均失败关闭。
- READY 不等于 ACTIVE；本项没有激活 Index，也没有修改公开 API、权限、依赖或外发边界。

## Migration / Compatibility / Rollback

- Migration：`20261004_0086`；仅增加/替换数据库函数和约束触发器，不新增数据列或公开 Contract。
- 空状态可降级到0085并恢复原 Build/Index 守卫；存在 SUCCEEDED/READY 或技术验证失败终态时拒绝降级，要求向前修复并保留证据。
- 兼容 Windows 11 / PostgreSQL 18.6 当前链路；Windows Server 2025、Debian 13、正式规模性能仍未由本项验证。

## Tests

- 空库 Schema0086 upgrade/down/re-up 与 Alembic drift 0。
- 正向：本地合成 1024 维单 Batch，HNSW/exact Top-1 10000 basis points；Validation PASSED、Job/Build SUCCEEDED、Lease RELEASED、Attempt 完成、Index READY，ACTIVE 数量仍为 0。
- 负向：直接完成 Job、直接推进 READY 均被数据库拒绝；受控强制 Recall 0 路径产生不可变 FAILED Validation，Job/Build/Index 同事务 FAILED；两类终态均拒绝降级。
- RAG Embedding/Migration/Metadata 定向 64 项通过。
- 后端全量 2438 项通过，3 项条件跳过。
- wheel 从可再生空 build 缓存构建、全新 venv 安装，确认产品从 wheel 导入，隔离 64 项通过；SHA-256 `bcb6d531593c544f6448a1dec090f7e12ed6a4f2c95d404400ef2449e252f946`。
- 零真实 Provider I/O、零客户数据外发、零 Secret 入库。

## Validation corrections

- 首次 P03 实库运行使用了新合成正文，但既有发送验证夹具内部仍固定校验 `PLM begin one`，在新 Owner 执行前因 payload 指纹不一致退出；临时数据库被回收。改回夹具原合成正文后，用全新数据库完整重跑 PASS/FAILED 两条路径，产品门槛未改变。
- 首次全量回归的 21 个既有 Windows 服务/进程测试失败，是 P02 空缓存 wheel 清理误删 editable 安装依赖的源码 `egg-info` 元数据所致。重新执行 `pip install --no-deps --editable apps/backend` 后，失败组 65 项与全量 2438 项均通过；最终 wheel 清理仅删除明确 build/临时目录并保留 editable 元数据。

## Known issues / Next

P03 只开放 READY。`RAG-03-A05-P04` 仍须登记一份未参与调优的新独立业务质量证据，满足分类不低于 90%、精确引用不低于 98%，并在当前来源/模型/授权仍有效时原子完成唯一 ACTIVE 切换。现有 POC-03 50 条已见集的 48%/74% 失败不能用于激活；Gate 3、UAT 和发行包保持未通过。
