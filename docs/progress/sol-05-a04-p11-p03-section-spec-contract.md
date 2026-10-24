# SOL-05-A04-P11-P03：SectionVersion Spec 声明兼容合同

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`CONTRACT_PASS_WRITE_CLOSED`。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `SOL-05-A04-P11-P03`，单一问题：可兼容请求及历史反读合同|
|输入基线|Gate 2 冻结 DM-05/API-04，CR-SOL-022；既有 Section CREATE/GET/LIST/VALIDATE DTO 与 0178 闭锁 Schema|
|前置|P11-P01 冲突已记录；P11-P02 在隔离 PG 升降/漂移、后端回归已验并同步|
|涉及模块/实体|Solution API/Application/Repository；SectionVersion 输入、历史视图与 SpecVersion 固定引用|
|涉及 API|现有 `/api/v1` 路径不变，可选加法字段；旧请求/首响必须保持原形与幂等摘要|
|涉及权限|CREATE 仍受 PM/实施成员、Session/CSRF/License；GET/LIST 保持既有项目读权限，不扩大|
|验收标准|未提供为 UNDECLARED 且不推定无需专项；显式 NONE_REQUIRED 有理由、FIXED_REFS 有界且去重；旧 GET/LIST 可反读；新声明在 Owner 安装前失败关闭；完整回归|
|风险|新增输入被现有旧 Owner 静默丢弃；冻结首响重放改变；旧草稿被当正式确认；跨项目 Spec 提前写入|

本片只确定并验收输入/读取形状；声明写入和当前 Spec 资格仍由 P11-P04/P05 承担。不得以纯 DTO 验收宣称新业务写功能可用。

## 结果与边界

- CREATE 增量解析 `spec_binding_state`、`spec_not_required_reason`、`structured_spec_refs`；缺字段维持 `UNDECLARED`。NONE_REQUIRED 必须有非空、规范化且有界的人工理由；FIXED_REFS 必须有 1～500 个固定 SpecSeries/SpecVersion 键，不允许重复/零 UUID。明确声明进入现有 CreateService 时先返回 `SOURCE_UNAVAILABLE`，在 Owner/资格证明安装前不留收据或 Audit，也绝不静默写旧结构。旧请求的字段集合、首次 201 响应与规范化幂等摘要完全保持原形。
- GET/LIST 历史只读加法暴露声明状态与固定引用计数；DETAIL 另返回理由/固定引用。Repository 锁定同 Project 的根与首次结果，按序重建固定 Spec 集合，不完整/重复/不匹配失败关闭。旧行显示 `UNDECLARED` 与空引用，不能推定 `NONE_REQUIRED`。
- 单元/合同定向 `27 passed, 82 subtests passed`；新增只读负例 `5 passed, 12 subtests passed`；后端完整回归 `3893 passed, 3 skipped, 6035 subtests passed`。隔离 Win11/PostgreSQL 18.6 先复验 P11-P02，再以真实 ORM 反读旧版本，伪造不完整引用后读取拒绝，脚本退出 0。

迁移：本片无新 Schema（继续使用 0178）。API 路径、权限和 License 不变；GET/LIST 新键为可选加法，旧 CREATE/首响稳定。回滚可移除新增 DTO/读取字段而保留 0178；不得删除历史。已知问题：正式声明写 Owner、同项目/适用性/现时资格/指纹与幂等首响关联，以及 Section/Outline Review 仍待后续独立验收；本片不是 Spec 维 PASS。
