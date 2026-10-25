# SOL-06-A06：四类专项载荷语义校验合同

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：冻结 DM-05 StructuredSolutionSpec 四类最小约束 → DEC-1201 → 0163 闭锁 payload → 本项。Phase 2；A02～A05 已验收。
- Changed：新增纯应用层 `validate_structured_spec_payload`，输入 `spec_type`/schema_version=1/JSON，返回不可变规范化 UTF-8 JSON 和 SHA-256；只生成有界版本候选，不写数据库或推定来源、Review、权限、AI 结论。拒绝未知字段/类型、非规范文本、超限/深嵌套、重复或缺失结构。

|类型|当前结构性最低合同|仍需 Owner 证明|
|---|---|---|
|PROCESS_MODEL|唯一 NodeId/Edge；一个 START、至少一个 END；无悬空边、孤立节点或不能到达 END 的路径；节点有角色/输入/输出|角色与真实职责、输入输出和 Evidence/Requirement 的现时可追溯性|
|INTERFACE_SPEC|系统边界、方向、数据责任、频率、错误/重试、鉴权与非空唯一字段映射|目标接口/凭据合法性及双方确认|
|MIGRATION_SPEC|来源/目标、范围、清洗规则、字段映射、试迁移、对账、回滚、验收标准|真实数据验证、备份可恢复及客户验收|
|PERMISSION_DESIGN|角色、资源、受限授权、`default_deny=true`、显式职责分离策略与可选角色分离对|最终权限矩阵、实际职责与冲突审查|

- 共同字段 `assumptions`/`exclusions` 为有界声明，不因 AI 填充而成为正式客户事实。规范化 JSON ≤1,000,000 字节，低于 0163 数据库 1 MiB 界；schema_version 严格为整数 1，未知类型/字段失败关闭。流程允许多个明确的 END；同一系统内部接口或迁移不人为禁止；单角色权限设计可显式写明无可分离职责。
- Verification：四类正例、快照不可变/字段顺序稳定、未知字段/深度/大小/文本、流程悬空/重复/不可达、接口边界/策略、迁移回滚/对账、权限默认拒绝/角色/职责分离等单元测试 9 项、39 子例通过；后端全量 3610 通过/3 跳过/5651 子例；开发 wheel 构建及该模块入包校验通过。本项纯校验无独立 API/权限或数据库行为，正式权限/来源另项验证。
- Migration/API/Permission：无迁移、公开 API 或权限变化；Root/refs/payload 仍由 0161～0163 全部闭锁。Rollback 为移除尚未装配的纯校验合同，既有业务历史不受影响。Gate3/Pilot/正式发行仍未通过。
