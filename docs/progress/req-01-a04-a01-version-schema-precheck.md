# REQ-01-A04-A01：RequirementVersion Schema 编码前核查

日期：2026-10-07。结论：`REQ_01_A04_A01_VERSION_SCHEMA_PRECHECK_PASS`。下一项：
`REQ-01-A04-A02` Version primary、同父替代链与正式指针组合 FK。

## 冻结对账

- REQ-03 是 V-PRJ 不可变版本，primary table 固定 `req_requirement_versions`；六类语义 owned table 固定为
  `req_sources`、`req_acceptance_criteria`、`req_capability_assessments`、`req_assumptions`、
  `req_exclusions`、`req_dependencies`，不合并为 JSON。
- Version primary 必须包含 Requirement/Project、正版本号、32字节内容指纹、共同版本状态、同父
  supersedes、创建人/时间；Requirement正式指针使用 `(version, requirement, project)` 组合FK，且在
  A08 Review正式化Owner前继续禁止非NULL写入。
- 版本业务快照包含 statement、rationale、domain、priority、risk、classification；分类固定四值。
  来源、能力判断、验收标准、假设、排除、依赖必须是固定集合，AI只能提供Draft provenance。
- A04只物理化并关闭Owner；A05证明来源资格，A06原子创建完整版本，A07验证分类/能力/验收规则，A08
  Review正式化。不得在Schema任务中提前批准或移动正式指针。

## 冲突与选择

- 冻结Domain列出`title`，冻结API的`RequirementVersionInput`最小请求未列title。为避免破坏已冻结请求，
  primary保留nullable title，但V1不新增必填请求字段；读侧显示以Requirement code和statement摘要组成。
  后续如要允许人工title，须采用兼容的可选请求字段并另行API CR，当前不实施。
- 冻结未枚举priority/risk。沿用已冻结实施域常用priority `LOW/MEDIUM/HIGH/URGENT`；risk采用
  `LOW/MEDIUM/HIGH/CRITICAL`。两者是字段值闭合，不增加业务Root或工作流。
- `dependencies`是版本内的文字/外部依赖声明，不代替A09的RequirementRelation DAG；两者不得互相推断。
- Evidence和AI provenance需要规范化支持引用表，属于六类集合的子引用而非新增Root；不得把核心归属、
  Scope或资格仅藏在JSON/UUID数组。A05/A06前这些写入口保持关闭。

## 实施拆分

1. A02：Version primary、同Requirement版本号/替代链、Root正式指针组合FK与关闭守卫。
2. A03：六类语义owned表及结构/顺序/同版本组合约束。
3. A04：Evidence/AI provenance支持引用、提交完整性和空/历史升降验证。

无Schema、程序、依赖、Secret、外发或客户事实变化；本项为冻结对账与可追溯实施决策。
