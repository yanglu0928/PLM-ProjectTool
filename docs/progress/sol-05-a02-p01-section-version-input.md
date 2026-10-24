# SOL-05-A02-P01：SectionVersion DRAFT 有界输入合同

日期：2026-10-09。结果：`SECTION_VERSION_INPUT_INTERNAL_PASS`；仅结构合同，不代表受权创建、正文来源或正式方案通过。

## 编码前检查与范围

Phase 2 Platform Core；输入 Gate2 冻结 DM-05/API-04、CR-SOL-003/0138 和 SOL-05-A01 前置，前置满足。单一问题是把 SectionVersion DRAFT 的固定输入规范化并生成稳定请求指纹。涉及 Solution Application 的 SectionVersion、Requirement 根/版本、Evidence ID 与受控正文引用；不访问 Document/Evidence/Project/Review 数据库，不改实体、权限、公开 API、ORM/Migration 或依赖。验收为正文引用二选一、标题/ID/重复/数量/声明 JSON 正反例、顺序和规范指纹稳定、输入声明不可被后续调用者修改。风险是结构通过被误称来源合格，或把 Artifact UUID 直接放入业务写入路径；后续 Owner 必须独立拒绝没有真实 OutputArtifact 证明的分支。

## 实施与验证

新增 `SectionVersionDraftInput`、`SectionRequirementRef`、`ValidatedSectionVersionDraft` 和 `validate_section_version_draft`。固定 Project/Section、NFC 非控制字符标题（1～500）、DocumentVersion/Artifact 二选一 UUID、最多500条不重复 Requirement 根/版本和 Evidence ID、两组最多100项且各不超过64KB的规范 JSON 声明；允许空固定引用作为待补的 DRAFT，不能由此推定 VALIDATE 合格。请求指纹绑定所有固定输入与顺序；声明深拷贝以免调用后变异。此合同接受 Artifact 的结构形状，但未挂任何公开写入服务，后续 Owner 在 OutputArtifact 证明前不得开放该分支。

定向 pytest `6 passed, 25 subtests passed`，覆盖规范等价、顺序变更、两正文分支及空/重复/超限/畸形负例。第一次后端全量 unittest 运行3482项，因所用虚拟环境缺 pytest 导致两个既有模块导入错误，不能记 PASS；改为在同一业务虚拟环境仅从本机现有测试环境补充 pytest 运行器后，全量 pytest `3502 passed, 3 skipped, 5423 subtests passed`、退出0。最终只增强本任务测试断言后定向 pytest 再次 `6 passed, 25 subtests passed`；未重新跑全量，应用代码未变化。未执行 PG/HTTP/浏览器测试，因为本项不写库或挂 API。

兼容性/升级/回滚：无 Schema/Migration/API/权限/配置/生产依赖/数据变化；撤未接线输入模块和单元测试可回滚，0138 历史与闭锁保持。已知问题：DocumentVersion 字节/状态、Requirement 当前批准、Evidence 项目/现时资格、Artifact/Spec、Review/Trace/Workflow 及正式目标环境均待后续 Owner；Gate3/发行继续 BLOCKED。下一项 `SOL-05-A02-P02` 先定义 DocumentVersion 正文现时证明的最小安全端口与负例，不直接解锁写表。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → SOL-05-A01 → DEC-1167 → 本合同 → Document/Requirement/Evidence Proof → SectionVersion Owner/Guard → VALIDATE/Review/Trace → Gate3。
