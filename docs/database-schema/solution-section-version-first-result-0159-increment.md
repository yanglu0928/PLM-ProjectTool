# SOL-05-A02-P09：SectionVersion 首响应闭锁表 0159 增量

日期：2026-10-09。依据 Gate2 DM-05/API-04、CR-SOL-003/P07；原冻结提交 `64cdf09` 和 0138 历史不改写。

`20261009_0159` 在 0158 后创建 `plm.sol_section_version_create_results`：以 SectionVersionId 为主键，并用 Version/Section/Project 三元 FK 绑定 0138 版本；固定首次 201 DRAFT 响应所需版本号、标题、DocumentVersion 或 ArtifactRef 二选一、32 字节指纹、假设/排除数组、引用数、前驱、创建人和时间。创建人有 User FK；版本号、标题、正文 XOR、摘要长度、数组类型、计数、前驱非自指、有限时间有 CHECK。表没有正文文件字节或 Locator。此时仅有字段形状与父版本身份约束，跨字段与父行值完全一致的证明留给 P10 INSERT-only Guard；不能把复合 FK 当成完整业务一致性。

新增独立 INSERT/UPDATE/DELETE 拒绝触发器和 TRUNCATE 拒绝触发器。0138 的 SectionVersion/Requirement/Evidence Guard 不改，公开 API、权限、配置和运行时依赖不变。P10 在空历史审计和真实同事务 Owner 证据就绪之前不得打开任何 DML。

迁移/回滚：空库可 0158→0159→0158→0159；已有 Project/Outline/Section 行不回填、不改写，升级和回退保留；首响应表非空时拒绝 0159→0158 降级，不能清除历史。若未来 P10 已有正式数据，先遵守 P10 的更严格非空拒降门禁。生产执行前仍须备份与目标账户演练，本次只验证可弃 Win11 PG。

验证：`validation/sol-05-a02-p09-section-version-first-result-schema/verify.py` 在 Win11 可弃 PG18.6 退出0：空/已有数据升级、空表降级重升、Alembic drift、复合 FK 与编号/标题/XOR/指纹/声明/计数约束、INSERT/UPDATE/DELETE/TRUNCATE 闭锁、非空首响应拒降。合成 SectionVersion 只用于临时库约束负例，经临时连接受控造数/清理，不代表正式 CREATE Owner 已安装。后端全量结果见 P09 进度记录。Server2025/正式账户、完整迁移演练、Gate3/发行仍未验。
