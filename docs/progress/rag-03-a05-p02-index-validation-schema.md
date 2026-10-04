# RAG-03-A05-P02：EmbeddingIndex 不可变技术验证证据

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_EMBEDDING_INDEX_VALIDATION_SCHEMA_PASS`

## Changed

- 新增 Schema0085 与 ORM `EmbeddingIndexValidationRow`；每个 Index/Build 至多一条验证记录，精确绑定 Scope/Project、Model/Dimension、source/build/record-set 指纹、记录与批次数量。
- 保存受控 HNSW catalog 指纹、实际计划指纹、`ef_search=200`、`iterative_scan=strict_order`、同 Scope/Project/Index exact 对照数量和 basis-points Recall，不保存查询正文、客户正文或 Golden 答案。
- 数据库提交前以数据库时间固化完成时刻，并重算 source/AVAILABLE record、缺失/额外/重复/无效记录、全部 Batch、record-set/HNSW catalog/validation 指纹与 Recall 汇总；只有当前未过期单次 RAG Job Lease 下的 RUNNING Build/BUILDING Index 才能写入。即使零可用记录，FAILED 也能用空记录集摘要留下不可变失败证据。
- PASSED 必须完整记录/批次、HNSW 与 exact 计划均观察到、实际 Recall 不低于绑定策略门槛；FAILED 必须有受控 `RAG_*` 错误。记录只允许 INSERT，UPDATE/DELETE/TRUNCATE 均拒绝。
- Schema0085 不修改 Build/Index/Job 状态；技术 PASS 形成后仍保持 RUNNING/BUILDING，P03 才负责原子完成并推进 READY。

## Migration / API / Compatibility

- Migration：`20261004_0085`；空表可降级到0084，存在任何验证历史时拒绝物理降级并要求向前修复。
- API：无公开 API 或冻结 Contract 变化。
- Dependency：无新增依赖。
- Compatibility：内部追加表；原冻结提交不改，现有 Index/Build/Batch/Record 历史不回填、不改写。
- Rollback：未产生验证记录时可降级；有历史时保留证据，不允许删除伪造回滚。

## Tests

- Windows 11 / PostgreSQL 18.6：空库 upgrade/down/re-up、已有 Index/Build 有数据升级、Alembic ORM drift 0。
- 使用本地合成非零 1024 维响应完成一个精确 Batch，记录 HNSW 计划、同范围 exact 计划及 Top-1 10000 basis-points 对照；写入技术 PASSED 后 Index/Build/Job 仍为 BUILDING/RUNNING/RUNNING。
- 错误 record-set/validation fingerprint、伪造客户端完成时间、历史 UPDATE/DELETE/TRUNCATE 和有历史 downgrade 均失败关闭；完成时间由数据库覆盖为当前语句时间。
- RAG Embedding 定向 50 项、Migration 4 项、Metadata 3 项通过。
- 后端全量 2431 项通过，3 项条件跳过。
- wheel 隔离 57 项通过；SHA-256 `f6971d1ec3eb529f5e5b8bb1513f99df68a490b202cf55052591e9ba17ca0779`。
- 零真实 Provider I/O、零客户数据外发、零公开 API。

## Validation corrections

- 首轮 HNSW/exact 对照使用全零合成向量，cosine 路径无法形成可靠相同候选；验证夹具改为非零 `0.01` 向量后使用全新数据库完整重跑，产品代码和门槛未放宽。
- 第二轮插入夹具漏传 expected/succeeded Batch 两个参数，修正参数绑定后全新数据库重跑。
- 首轮全量测试误用缺少 `pydantic-settings` 的精简 Python 环境，同时发现 Metadata 历史清单未排除新表；补清单并改用完整锁定 Python 3.13 环境后全量重跑通过。
- 首轮 wheel 子 venv 未继承构建运行时依赖，导入失败；确认 wheel 包来源后以锁定依赖运行时作为只读 dependency path 重建全新 wheel/venv，57 项完整通过。临时 wheel 目录已清理。
- 最终收紧后首次 wheel 脚本使用当前 PowerShell 不支持的 `Select-Object -Single`，构建成功但安装前退出；安全清理该次临时目录及构建缓存，改用单元素计数后从空构建目录重跑，wheel 导入和 57 项验证通过。

## Known issues / Next

Schema PASS 不表示 Build 已完成、Index READY/ACTIVE、正式性能或业务质量通过。下一项 `RAG-03-A05-P03` 实现技术验证 Owner 与 Build/Job/Index READY 原子收敛；业务 ACTIVE 仍由 P04 的新独立质量证据控制。Windows Server 2025、Debian 13、Gate 3、UAT 和发行包保持未通过。
