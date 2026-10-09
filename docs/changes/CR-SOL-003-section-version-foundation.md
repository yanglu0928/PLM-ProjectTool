# CR-SOL-003：SolutionSectionVersion 内容/来源分层持久化

日期：2026-10-08；状态：依据 CR-EXEC-001 持续授权先记录后实施；Gate 2 原冻结提交 `64cdf09` 不改写。TraceLink：CR-SEQ-001 → SOL-01-A02/A03-P01 → 本 CR → SOL-01-A03-P02。

## 来源与差异

冻结 DM-05、SC-01/02、API-04 要求 SOL-05 独立不可变 SectionVersion，固定受控正文、需求、Evidence、StructuredSpec、Review 与状态；正文不复制到关系表。当前仅有 Section 身份，没有 `sol_section_versions`。DocumentVersion/RequirementVersion/Evidence 已存在，但 Evidence 的 GLOBAL/PROJECT 当前资格不能由单一 FK 证明；StructuredSpec 与 OutputArtifact 的真实 Owner 尚未建立。直接保存无类型的正文 UUID、Evidence 视作客户确认或提前开放写入，均不符合冻结边界。

## 方案比较与选择

- 不选单文本字段/裸 UUID 或让 OutlineVersion 代表全部章节：缺固定正文与独立 Review，无法反向 Trace。
- 不选等全部 Spec/Output 功能后才建立任何章节结构：已有 Document/Requirement/Evidence 可先形成可验证的约束基础。
- 选择 `SOL-01-A03-P02` 增加章节版本根、固定 RequirementVersion 与 EvidenceRef 子表；正文以 `content_document_version_ref` 或 `content_artifact_ref` 二选一保存，前者有真实 DocumentVersion FK，后者在 OutputArtifact Owner 未就绪前仍由闭锁触发器阻止。章节批准指针补同 Section/Project 复合 FK。Spec 引用待 SOL-06 后补建复合 FK；这是一项施工时序差异，不删除冻结功能。版本写入、Evidence 项目/当前性、正文文件完整性、Requirement/Trace 一致及 Review 均由后续真实 Owner 验证，当前数据库 DML 全拒。

## 影响、迁移与验证

- `20261008_0138` 在 0137 后增加三个空表及 Section 指针 FK；无公开 API、权限、依赖、配置、客户数据或外发变化。Root 保存 SHA-256 指纹、标题、声明数组、声明引用数、同父替代链和 Review 引用。正文二选一 CHECK；DocumentVersion 有 FK，Artifact 分支不得在对应 Owner 接入前开放。
- 空库/含现有项目数据升级、空表降级重升、Schema drift；非空版本/子表拒降，不得丢历史。回滚仅适用于新三表无数据，保留既有 Outline/Section 身份及目录版本。
- 隔离 PG18 必测内容二选一、DocumentVersion FK、同项目 RequirementVersion FK、引用顺序/重复、Evidence FK、跨 Section 指针、非法标题/指纹、未装配 Owner 和 TRUNCATE 闭锁；后端全量回归。缺 Spec/Output/人工 Review 事实前，Phase 2/Gate 3 与 Solution 正式链保持 OPEN。

## 2026-10-09 后续输入切片

SOL-05-A01 核查确认 0138 闭锁仍在、无 SectionVersion 写 Owner；SOL-05-A02-P01 按 DEC-1167 增加仅限内部的 DRAFT 有界输入/稳定请求指纹，DocumentVersion/Artifact 引用二选一、固定 Requirement/Evidence 与声明形状单元及后端全量回归通过。该结构校验不证明当前来源、权限或 Review，Artifact 分支无 OutputArtifact Owner 时不得进入写路径；未修改 0138、冻结 API、权限或 DML Guard。见 `docs/progress/sol-05-a01-section-version-precheck.md` 和 `docs/progress/sol-05-a02-p01-section-version-input.md`。本 CR 继续 OPEN，后续受控 Owner/Guard、迁移和回滚必须先补具体计划并独立验证。

SOL-05-A02-P02 按 DEC-1168 增加仅限内部的 PROJECT DocumentVersion 正文固定身份/物理字节证明适配器，定向与全量后端回归通过；未挂 SectionVersion Owner 或解锁0138，且不把文件可用误称章节已批准。见 `docs/progress/sol-05-a02-p02-section-document-content-proof.md`。本 CR 保持 OPEN。
