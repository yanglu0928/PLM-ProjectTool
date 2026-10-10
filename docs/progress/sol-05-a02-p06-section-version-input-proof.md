# SOL-05-A02-P06：SectionVersion DRAFT 输入同事务组合证明

日期：2026-10-09。结果：`SECTION_VERSION_INPUT_COMPOSITION_INTERNAL_PASS`；仅 Application 内部编排，不授予创建权限或解除 0138 写闭锁。

## 编码前检查

当前 Phase 2 Platform Core、WBS `SOL-05-A02-P06`。输入基线：Gate2 冻结 DM-05/API-04、CR-SOL-003/0138 与 P01～P05 的有界输入、Document/Evidence/Requirement/Section 当前证明。前置满足。单一问题是同一调用者事务内组合这些证明，形成稳定、包含现时来源的章节版本指纹。涉及 Solution Application 的 SectionVersion DTO/端口；不改上游 Owner、Schema/Migration、公开 API、权限或技术栈。验收包括固定调用顺序和事务对象、正反例、来源变更指纹变化、Artifact 分支失败关闭。风险是把内部来源证明误报为项目授权、内容质量、正式 Review 或真实写入。

## 实施与证据

新增 `SectionVersionInputProofService`：先验证 DRAFT 输入和 Session/Trace 形状，再拒绝无 OutputArtifact Owner 的 Artifact 分支；随后在原事务中核对 Section/Outline 当前基底、PROJECT DocumentVersion 物理摘要、当前批准 RequirementVersion/Review 身份以及 Evidence 的 PROJECT 固定来源投影。严格核对每个端口返回的类型、Project/固定 ID、序列和32字节摘要；异常对外只保留 `SOURCE_UNAVAILABLE`，不暴露原文件名或 Locator。规范指纹包含请求指纹、下一个版本/前驱、Document 摘要、每项 Requirement 审批事实及 Evidence 版本/锁/摘要；它是版本输入固化指纹，不等于正文语义质量。

定向 pytest `6 passed, 29 subtests passed`，覆盖同一事务/顺序、空可选引用、输入/Artifact失败关闭、全部端口跨项目/坏ID/坏摘要/状态元数据负例及来源变化指纹；后端全量 pytest `3525 passed, 3 skipped, 5500 subtests passed`、退出0。P05 可弃 PG 基底与 P02～P04 上游证明已有独立验证，但本新组合服务仍是单元桩测试；未运行真实 SectionVersion PG 写链、HTTP 或浏览器，不能据此判最终 SOL-05/Gate3 PASS。

额外尝试复跑旧 `validation/sol-01-a03-p02-section-version-schema/verify.py` 未通过：当前 head 的后续 0146/0148 首响应闭环使旧测试造数不再成立；临时修复造数后，向 0137 回退又先被 0148 的 Section 历史不可降级门禁拦住，无法到达旧脚本预期的 0138 拒降断言。临时修复已撤回，旧脚本未计本项 PASS、未改产品 Schema/Guard。作为当前 head 的替代直接证据，在 P05 可弃 PG 验证资产中新增 0138 写 Guard 拒绝断言并重跑退出0，确证本项没有意外开放 SectionVersion DML；这不替代旧脚本完整迁移验收，未来仍须更新该历史验证策略，而不是弱化不可降级约束。

兼容/升级/回滚：新增未接线应用模块和测试，无 Schema/Migration/API/角色/配置/依赖/数据变化；撤本模块可回滚，原冻结基线与 0138 Guard 不变。下一项 `SOL-05-A02-P07` 先核查受权 CREATE、不可变首响应收据及写 Guard 的具体迁移/回滚前置，再实施真实 Owner。正式信任/Server2025、性能、POC-03质量、Gate3/发行仍未通过；Debian13 实机依用户指令跳过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → SOL-05-A02-P01～P05 → DEC-1172 → 本组合证明 → CREATE Owner/Guard → VALIDATE/Review/Trace → Gate3。
