# SOL-04-A06：SolutionSection 只读链前置核查

日期：2026-10-09。结果：`SOL_04_A06_SECTION_READ_PRECHECK_PASS`，仅静态前置核查与施工顺序；GET/LIST 未实现、未运行新测试。

## 输入与证据

- Phase/WBS：Phase 2 Platform Core / SOL-04-A06。输入为 Gate 2 冻结 API-04 `SOL_SECTION_GET/LIST`、DM-05、0136/0148 Section 表、A03～A05 创建链及现有 Outline 只读模式。
- `sol_sections` 已有稳定 SectionId、ProjectId、OutlineId、key、状态、批准指针、创建人/时间、锁版本；同项目 Outline FK、同 Outline key 唯一与状态索引已在 ORM/迁移中。0148 仅开放初态 INSERT，后续 PATCH/ARCHIVE/Version/Review 未装。
- `ProjectAuthorizationService.POLICIES` 有 Outline GET/LIST 与 Section CREATE，但没有 Section GET/LIST。Solution 模块没有 Section 读取 Owner/仓储/HTTP 或列表签名游标；`production_login` 仅在写模式装 Section CREATE。不得把 Section 创建后 Location 解释为 GET 已可用。
- 冻结合同要求 GET 单 Section 给当前 Project member、LIST 给 Project member；两者均为只读，不能从 Section CREATE 的 PM/实施成员写策略推导权限。Section 初态批准指针 NULL，不能把 Section 身份当作已审批正文或 Requirement 覆盖证明。

## 施工顺序与验收

1. `SOL-04-A07` 单独实现 Section 当前详情内部只读 Owner/仓储与项目成员策略。锁当前成员事实，查询只允许同项目 Section，返回最小身份/状态/批准指针/ETag；非空指针必须复验属于同 Section 且已通过 Review，未接线前不推断为批准。验证跨项目、客户当前成员、暂停成员、归档对象、License/异常及真实 PG。
2. `SOL-04-A08` 可选 GET HTTP，严格 Session/Origin/Trace/ETag/no-store，默认 404；真实 ASGI/PG 验证。
3. `SOL-04-A09` Windows 显式只读/写模式注入 GET，登录专用仍 404；目标账户信任源另验。
4. LIST 独立拆 Owner/keyset、专用签名 cursor 与 Vault 供给、可选 HTTP、Windows 组合；不得复用 Outline cursor 或无签名暴露分页。
5. Section PATCH/ARCHIVE、Version/Review/Trace、前端/浏览器后续各按单独 WBS；真实业务确认与 Gate3 不因此通过。

本核查无程序、Schema、Migration、公开 API 或依赖变动；无需新 Change Request，因仅细化冻结合同施工顺序。若发现批准指针消费需要改变冻结 Review/Schema，实施前另登记 CR。静态检查不替代运行测试。正式目标账户/License、Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
