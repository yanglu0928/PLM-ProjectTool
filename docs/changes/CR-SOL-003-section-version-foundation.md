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

SOL-05-A02-P03 按 DEC-1169 复用 Requirement-owned 的当前批准版本证明，并复跑既有 Win11 隔离PG脚本通过；不新增重复查询或把批准需求推定为章节覆盖。见 `docs/progress/sol-05-a02-p03-section-requirement-use-proof.md`。本 CR 保持 OPEN。

SOL-05-A02-P04 按 DEC-1170 增加仅限内部的 PROJECT Evidence 现时/物理来源最小投影，严格限定 PM/实施成员并屏蔽 Locator/原文件名；定向、后端全量与上游 Evidence 隔离PG脚本通过。新适配器尚未接入真实SectionVersion PG写链，0138仍闭锁；见 `docs/progress/sol-05-a02-p04-section-evidence-use-proof.md`。本 CR 保持 OPEN。

SOL-05-A02-P05 按 DEC-1171 增加 Section/父 Outline 同事务、同项目、活动态和批准指针/版本序列基底证明，固定 Outline→Section 锁顺序；定向与 Win11 可弃 PG18.6 正反例通过。此端口不验完整历史链/正式授权，也不解除 0138 写闭锁；见 `docs/progress/sol-05-a02-p05-section-version-base.md`。本 CR 保持 OPEN，未来 Guard 解锁须独立迁移/回滚与真实写链验证。

SOL-05-A02-P06 按 DEC-1172 将有界 DRAFT 与 Section、Document、Requirement、Evidence 现时证明组合为同事务内部输入指纹；Artifact 裸引用无真实 Owner 时失败关闭。定向与后端回归通过后仅标内部编排，不宣称真实 PG 组合写链；当前 head 可弃 PG 直接复核 0138 写闭锁。旧 0138 完整脚本受后续 Owner 闭环/拒降门禁影响复跑未通过，保留诊断而不弱化约束。见 `docs/progress/sol-05-a02-p06-section-version-input-proof.md`。本 CR 保持 OPEN。

SOL-05-A02-P07 按 DEC-1173 先完成 CREATE/Guard 前置审查。差异：Project 授权操作、不可变首响应表和 INSERT-only Owner Guard 尚缺；Artifact/Spec 来源 Owner 尚缺，首个可写切片仅允许已有物理证明的 PROJECT DocumentVersion。选定 P08 授权 → P09 闭锁首响应 ORM/Migration → P10 空历史前提下 Guard/提交闭环迁移 → P11 同事务 CREATE Owner/收据/Audit → P12 HTTP/Windows。影响为增量 Schema/权限/数据写入；原 0138 冻结内容不改写。迁移须空库与既有 Section 数据升降重升、drift、DML 负例；非空版本/收据/子表禁止降级并保留历史，异常存量先审计；Owner 须真实 PG/ASGI 并发、重放、授权、来源失效及回滚验证。不得先解锁再补证据，Review/Trace/Artifact 后续独立验收。详见 `docs/progress/sol-05-a02-p07-section-version-create-precheck.md`。本 CR 保持 OPEN。

SOL-05-A02-P08 已按冻结 API-04 补 Project-owned `SOL_SECTION_VERSION_CREATE` PM/实施成员写策略及角色/非成员/归档负例；仍无调用方/入口，0138 全拒写不变。见 `docs/progress/sol-05-a02-p08-section-version-create-authorization.md`。P09 首响应闭锁表是下一前置，本 CR 保持 OPEN。

SOL-05-A02-P09 按 DEC-1175 新增 `20261009_0159` SectionVersion 首次 201 DRAFT 结果闭锁表及 ORM。复合 FK/自身 CHECK 只证明形状和版本身份，P10 才能将结果字段与版本/引用集合做同事务完整性绑定；此时全部 DML/TRUNCATE 仍拒绝。可弃 PG 验证空/已有 Section 数据升级、空表降级重升、非空结果拒降、约束与 drift；正式数据不回填、不删除。详见 `docs/database-schema/solution-section-version-first-result-0159-increment.md` 和 `docs/progress/sol-05-a02-p09-section-version-first-result-schema.md`。本 CR 保持 OPEN。

SOL-05-A02-P10 实施前差异记录（待验证）：0159 的四表 INSERT 仍全拒，P11 无法在一事务保存章节版本、固定引用和不可变首次响应。拟新增独立 0160 迁移，在四表全空审计后将 INSERT 改为受限写入：Outline→Section 锁序、ACTIVE/同项目、DRAFT/无 Review、DocumentVersion-only、连续版本链、声明数组/引用数及有序引用、首响应全字段一致，并用延迟触发器在提交时拒绝缺引用/缺首响应。UPDATE/DELETE/TRUNCATE 仍全拒；Artifact/Spec 分支继续关闭，现时 Document/Requirement/Evidence 资格由 P11 同事务 Owner 证明。空表可回退 0159，任一版本/固定引用/结果有历史时拒降，异常已有行不自动清除而要求独立审计迁移。验证计划为 Win11 可弃 PG18.6 空/已有 Section 数据升降重升、写入正反例/闭环失败回滚/漂移和后端回归；未通过前不标 P10 PASS 或开放 P11。

SOL-05-A02-P10 实施结果：按上述计划追加 `20261009_0160`，P09/0138 迁移文件不改；独立可弃 PG 验证空/已有 Section 升级、异常已有版本拒升、空表降级重升、Document 正常提交、Artifact/跳号/缺固定引用或首响应/结果不匹配整事务拒绝、历史不可改删、非空拒降与 Schema drift 通过。首次验证在根表 TRUNCATE 遇到 PostgreSQL 外键先行拒绝而非期望文案，调整测试为接受数据库层拒绝后全新库重跑通过，不改变生产约束。后端首次全量发现离线 SQL 渲染合同失败，已恢复仅离线渲染而在线仍审空历史，定向 4 项和 PG 脚本复跑通过；最终全量 3526 通过、3 跳过、5510 子测试。P11 Owner/正式环境和 Gate3 不因 Guard PASS 放行。详见 `docs/database-schema/solution-section-version-create-guard-0160-increment.md` 与 `docs/progress/sol-05-a02-p10-section-version-create-guard.md`。本 CR 保持 OPEN。

SOL-05-A02-P11 按 DEC-1177 新增内部受权 CREATE Owner/SQL 仓储，复用 0160 四表闭环及通用持久收据、Audit；仅 DocumentVersion 正文，Requirement/Evidence 固定引用同事务落库。当前 Session/License/Project 权限每次重验；完成收据从不可变首次响应重放，不以来源当前状态重构原始结果。Windows 11 可弃 PG18.6 真实适配器合成组合覆盖经理/实施成员、非空 Requirement/Evidence、来源失效、跨项目、Artifact 关闭、同/异 Key 并发和失败回滚；Review APPROVED 来源为隔离合成夹具，非客户签署。测试曾用不可逆 REVOKED 试图恢复，改用可恢复 INELIGIBLE 后复跑通过，生产约束不变。无公开 HTTP/Windows 接线、Schema/权限/依赖变化，P12 与正式环境独立验收；本 CR 保持 OPEN。详见 `docs/progress/sol-05-a02-p11-section-version-create-owner.md`。

SOL-05-A02-P12-P01 按 DEC-1178 增加冻结路径的可选 POST 边界与 Windows 显式写模式组合；完整 P12 的真实 Edge/网络尚待 P02，不以 ASGI TestClient 代替浏览器。严格请求与 201 DRAFT 首响应/错误映射，默认 404，缺 Document/来源依赖失败关闭；一次性 ASGI/PG 验证当前会话、同键重放、实施成员、来源篡改及 SQL/Audit 数量通过。无 Schema/API Breaking/依赖/权限变化，可撤可选装配，正式历史不删；详见 `docs/progress/sol-05-a02-p12-p01-section-version-http-windows.md`。本 CR 保持 OPEN。

SOL-05-A02-P12-P02 按 DEC-1179 补真实 Edge→Uvicorn loopback→PG18.6 验收。合成现时来源和 Cookie 下观察 201/重放/409/404/403/422/503，SQL 证实仅一条新增版本/首响应/收据/Audit；仅测试资产、无生产变化。未验证正式 HTTPS、服务账户/公钥、Server2025 或 UI，也不解除旧 0138 完整脚本诊断和 Gate3 阻塞。详见 `docs/progress/sol-05-a02-p12-p02-section-version-edge-network.md`。本 CR 保持 OPEN。

SOL-05-A03-P01 按 DEC-1180 开始独立历史读取，先补冻结 API-04 的项目成员 GET/LIST 只读授权并锁定当前事实；尚无 Owner/HTTP，不把 CREATE 首响应或历史固定引用当作现时资格。无 Schema、API Breaking、依赖/数据变化；见 `docs/progress/sol-05-a03-p01-section-version-read-authorization.md`。本 CR 保持 OPEN。
