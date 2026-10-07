# CR-PRT-001：Prototype 运行时基础与受控制品边界

日期：2026-10-08。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交
`64cdf09` 保留；本 CR 实现冻结 PRT-01～PRT-05，不把 AI 输出、模板、未校验制品或需求链接描述成
Approved PrototypeVersion。

## 来源、冲突与当前缺口

冻结 Data Model/Schema/API 已定义 PrototypePackage、Prototype、PrototypeVersion、PrototypeTemplate、
RequirementPrototypeLink，API-04 固定 26 个 Operation，并要求 PrototypeVersion 只引用 Approved
RequirementVersion、固定 TemplateVersion 和受控 Artifact。当前仓库没有 `prototype` 模块、`prt_*` 表、
Migration、业务 Owner、Review Subject、Router 或页面；Trace、Audit、AI Task 和 Workflow 中的预留只证明
允许的边界，不构成 Prototype 实现。

实施方案摘要仍列出旧的 `/prototypes/generate`，与 Gate 2 后冻结的项目级资源/版本合同冲突。按仓库优先级
采用冻结 API-04：`PROTOTYPE_GENERATE` 只能经统一 AIService/AITask 产生建议态或 Draft 输入，不另开旧
快捷路径，不执行生成代码，也不能越过 Artifact 校验、人工编辑、Review 和正式指针更新。

## 选择

- 保持 PRT-01～PRT-05 Root、26 个 Operation、角色和错误语义不变；按 Identity/Template/Version/Link/
  Review/HTTP/UI 分层开放，不用一个 generate 命令跨越范围决定、生成、校验和审批。
- PrototypeVersion 采用逻辑身份 + 不可变版本；正式指针只由 `PRT-03 + PROTOTYPE_ALL_V1` Approved Review
  终态消费更新。AI 生成结果保持 Draft，历史版本和固定引用永久保留。
- `NOT_REQUIRED` 是 Prototype Root 上的显式范围决定，必须固定受影响的 Approved RequirementVersion、
  reason、impact、决定/Review 与 Evidence；无 PrototypeVersion 或无 Link 不能被推断为“不需要原型”。
- Template 创建时固定 GLOBAL/PROJECT Scope，修订产生新 TemplateVersion；GLOBAL 模板不得反写项目事实。
  首版只把模板当受控输入，不增加模板市场、任意脚本或执行沙箱。
- RequirementPrototypeLink 两端固定同项目不可变版本，purpose 仅
  `ILLUSTRATES / VALIDATES / ACCEPTANCE_REFERENCE`；覆盖判断同时重验 Link、Version 自带 RequirementRef、
  Artifact 当前可访问性/完整性及 Review，不以任一单表投影代替完整证明。

## 实施拆分

1. `PRT-01-A01`：本 CR、冻结对账、差距及兼容/迁移/回滚计划。
2. `PRT-01-A02`：Package/Prototype identity、membership 与 NOT_REQUIRED decision Schema/Migration。
3. `PRT-01-A03`：Package/Prototype identity Owner、状态、显式范围决定、持久结果与 Audit。
4. `PRT-01-A04`：GLOBAL/PROJECT Template、不可变 TemplateVersion 与 ArtifactRef Schema/Owner。
5. `PRT-01-A05`：PrototypeVersion、Artifact/Requirement/Interaction owned 数据 Schema/Migration。
6. `PRT-01-A06`：Approved Requirement、固定 Template、Artifact/Evidence 证明及 Version create/read/validate。
7. `PRT-01-A07`：`PRT-03 + PROTOTYPE_ALL_V1` Review 送审、终态正式化和 Trace Owner。
8. `PRT-01-A08`：RequirementPrototypeLink Schema、生命周期、覆盖不变量与 Owner。
9. `PRT-01-A09`：冻结 HTTP、Windows 显式组合与真实 PostgreSQL 18 验证。
10. `PRT-01-A10`：前端范围决定、模板选择、制品定位/人工维护提示与真实 Edge 闭环。
11. `PRT-01-A11`：`PROTOTYPE_SCOPE_DECISIONS/PROTOTYPE_COVERAGE` Workflow 资格及相邻推进。

`PROTOTYPE_GENERATE` 的统一 AI Task 接入放在 A06 的 Draft 输入边界内验证；它不是额外公开 Prototype
Operation，也不允许自动正式化。若后续需要新的建议读取/采纳 API，必须单独 CR，不静默扩展 `/api/v1`。

## 迁移、兼容与回滚

- 每个数据库增量必须含 ORM、Alembic up/down、空库与有数据升级、约束负例、drift 和历史拒降。
  无历史可逐级降级；产生 Prototype/Template/Review/Link 历史后拒绝破坏性物理降级。
- 新 Router 默认不装配，直至 Owner 与真实 PostgreSQL 证据完成；冻结 `/api/v1` 只做兼容实现，不改
  path/角色。PATCH 后续必须按冻结控制仅使用强 `If-Match`，不得由服务器伪造幂等 key。
- 应用回滚可移除 Prototype Router、页面、Workflow 注册与 AI Draft 接线，但不得删除历史 Version、
  Decision、Review、Artifact、Link、Trace 或 Audit。
- 无新增依赖、Secret、客户数据外发、License 或目标环境变化。Windows Server 2025 当前未跑本轮链，
  Debian 13 按用户指令跳过；Windows 11 结果不能被外推为其他平台实机通过。

## 验证与关闭条件

逐项执行定向 Unit/API/Permission/Exception、Windows 11/PostgreSQL 18.6 空库/有数据升降级、约束与并发、
真实 HTTP/Edge、完整后端/前端回归、wheel 和 Secret 扫描。A11 之前不宣称 Prototype Workflow 合格；
Gate 3、UAT、发行与可使用程序包仍以各自客观证据关闭。
