# CR-CAP-001：Capability 运行时基础与来源集合引用物理化

日期：2026-10-05。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09` 保留；Gate 3、Phase 4 与客户能力基线均未通过。

## 来源与冲突

冻结 DM-05 要求 `CapabilityBaseline.source_collection_ref` 指向标准能力库受控来源集合，BaselineVersion/CapabilityItem 又必须引用固定 GLOBAL Evidence 与 DocumentVersion。冻结 SC-01/SC-02 只列出 `cap_baselines`、`cap_baseline_versions`、`cap_items`、`cap_item_evidence_refs`、`cap_item_document_refs`，没有 SourceCollection Root/表或对应 Owner。当前生产源码也没有 capability 模块、表、Migration 或 Owner Port；只有 Audit 白名单、SC-04 表名清单和 API-04 合同。

若直接保存任意 UUID/字符串，会产生无法验证的悬空正式来源；若新增共享 SourceCollection Root，会扩大冻结 Root/Owner/Schema Scope；若把 RAG Index 当来源集合，会混淆知识索引代次与正式 DocumentVersion 事实。

## 方案比较与选择

- 不选新增 SourceCollection Aggregate/共享表：冻结模型没有该 Root，且会引入新的生命周期、权限和 API。
- 不选把 `EmbeddingIndex` 或可变“当前文档”当正式来源：Index 是运行系统事实，不能替代固定文档版本。
- 不选不受控 opaque ref：无法证明引用集合未漂移。
- 选择在 Capability Owner 内把 `source_collection_ref` 物理化为 `sha256:<64 lowercase hex>`。摘要由排序后的精确 GLOBAL `DocumentVersion` UUID 集合及合同版本计算；Baseline 保存当前受控集合引用，BaselineVersion 另保存自身 `source_collection_ref`，`cap_item_document_refs` 和 `cap_item_evidence_refs` 保存逐项固定引用。Owner 在创建/验证版本时通过 Document/Evidence Port 重算并要求全部为 `STANDARD_CAPABILITY`、GLOBAL、当前可访问且摘要一致。

该选择保持语义为“受控来源集合引用”，但不新增 Root、共享 registry 或公开 API 字段。项目只能读取已批准固定版本；Draft、AI Suggestion、现有标准能力文件和历史 R1～R11 成果不会自动正式化。

## 实施分解

1. `CAP-01-A02`：新增 Schema0091/ORM，建立两 Root 与三 owned tables；版本/Item/引用内容写保护，正式指针默认空，状态转换暂不开放。
2. `CAP-01-A03`：实现 DeploymentAdmin 内部 Baseline/Draft Version 创建、Document/Evidence 当前事实重验和验证报告；同事务 Audit/幂等另按既有平台合同接线。
3. `CAP-01-A04`：实现 Capability 的 Review Subject read/start/transition Owner 与 ReviewCompleted 原子消费，只有真实 APPROVED 版本可更新正式指针。
4. 后续独立任务再开放冻结 API-04 读写 HTTP、Windows 生产组合和前端；不会在 Schema 任务提前开放。

## 迁移、回滚与验证

- Schema0091 只新增表、索引、约束和写保护，不迁移或推断现有标准能力资料；数据库初始正式指针为零。
- 无 Capability 历史时允许降级；任何 Baseline/Version/Item/来源引用历史存在时拒绝物理降级，须向前修复或从受控备份恢复。
- 验证覆盖空库及有数据历史库升级、降级/重升、ORM drift、GLOBAL/Project 负例、集合摘要漂移、跨 Baseline、版本不可变、Item 稳定身份/代码唯一、悬空 Evidence/Document、非法正式指针和历史拒降。
- 应用阶段另覆盖 DeploymentAdmin、Session/License/CSRF/ETag/幂等/Audit、Review 锁/退回升版、项目只读与跨 Scope 隐藏。

## 风险与剩余边界

摘要只能证明已选固定引用集合一致，不能证明文档内容正确、能力项抽取质量或人工批准。Document/Evidence Owner 未通过前版本不能验证/送审；Review Owner 未完成前正式指针必须保持空。正式标准能力仍需有 GLOBAL 权限的人工作成并完成 Review；不得从本地资料、AI 输出或历史表格自动生成客户事实。Gate 3质量、性能、正式信任、Server 2025当前链和Debian 13发行验证不因本 CR 改变。

## 实施进度

- 2026-10-05 / `CAP-01-A02`：Schema0091/ORM已实施并在Windows 11/PostgreSQL 18.6验证；两Root/五表、来源集合重算、逐项Document/Evidence完整性、Owner关闭和历史拒降通过。没有导入资料、创建APPROVED或开放API。下一项按本CR进入A03内部创建与来源验证Owner。
- 2026-10-05 / `CAP-01-A03-P01`：A03按冻结三个独立Operation拆为P01 Baseline创建、P02完整Draft Version创建、P03 Validate报告；P01已实现DeploymentAdmin/License/幂等/Audit原子Owner，并经Document Port重验GLOBAL标准来源。无Schema/API/导入/正式状态变化，下一项P02。
- 2026-10-05 / `CAP-01-A03-P02`：为冻结M控制新增Schema0092最小Baseline锁推进守卫，完整DRAFT Version/Item/Document/Evidence Owner已通过Win11/PG18.6验证；来源和内容摘要均服务端计算，无Review/APPROVED/API/导入。下一项P03 Validate报告。
- 2026-10-05 / `CAP-01-A03-P03`：Validate Owner以不可变AuditEvent承载幂等历史报告，不新增冻结模型外结果表；当前PASS/失效、恢复后原Key回放与新Key重验通过。A03完成，下一项A04 Review/正式状态Owner。
- 2026-10-05 / `CAP-01-A04-A01`：核查确认Review Schema/ORM/只读仓储已有GLOBAL合同，但写服务、持久DTO与Subject合同被实现为PROJECT-only；登记`CR-RVW-003`，按GLOBAL内核、Capability Subject Owner、终态正式化三项补齐，不伪造Project、不跨Owner写表、不改变既有PROJECT API。下一项A04-A02。
