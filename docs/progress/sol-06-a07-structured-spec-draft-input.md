# SOL-06-A07：专项版本草案与固定引用输入合同

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：冻结 DM-05/SC-01 SOL-06 → 0161 Root/0162 refs/0163 payload → A06 类型校验 → 本项。当前 Phase 2。
- Changed：新增 `StructuredSpecDraftInput`/`ValidatedStructuredSpecDraft` 纯应用合同，组合 PROJECT 身份、初版或前驱升版配对、四类结构化 payload、顺序固定的 RequirementId+VersionId、SectionId+VersionId、EvidenceId、OutputArtifactId；只接受非零 UUID、不可重复逻辑身份/版本、每版至少一个固定需求和章节。证据和附件可为空；这不表示可送审。规范化载荷快照不可变，稳定请求指纹绑定项目/series/前驱/类型/schema/载荷摘要与每个引用的顺序。
- 安全边界：本合同只检验输入身份形状，不访问其他模块内部表、不证明现时来源资格、项目授权、Review、Trace、附件是否存在或客户确认。`OutputArtifact` Root 尚不存在，非空 ArtifactId 必须由未来 Owner 失败关闭直至真实目标证明接入；不存在受权创建入口。Root/refs/payload 保持 0161～0163 写闭锁。
- 验收：初版与升版配对、快照防外部变更、字段顺序稳定/引用顺序敏感、项目/UUID/重复/空来源/类型/载荷负例；定向 14 项/59 子例、后端全量 3615 通过/3 跳过/5671 子例；开发 wheel 构建及模块入包通过。无 Migration/API/权限变化；移除未装配合同可回滚，旧历史不受影响。
- 下一项：`SOL-06-A08` 明确来源资格与写 Owner 前置；先建立真实同项目 Requirement/Section/Evidence 证明和 OutputArtifact 缺口处理，不以结构校验直接开放专项。Gate3/Pilot/正式发行未通过。
