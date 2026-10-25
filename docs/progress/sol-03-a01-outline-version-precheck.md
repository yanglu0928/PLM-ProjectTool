# SOL-03-A01：SolutionOutlineVersion 正式写入前置核查

日期：2026-10-09。结果：`SOL_03_A01_PRECHECK_COMPLETE_WITH_DEPENDENCIES`；仅完成证据对账，`SOL_OUTLINE_VERSION_CREATE` 仍 `PRECONDITION_BLOCKED`，不标运行 PASS。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / `SOL-03-A01`。
- 输入基线：Gate 2 冻结 API-04、DM-05/SC-01/02、CR-SOL-002、0136～0138、0146；SOL-02 目录身份 CREATE/GET/LIST 及 Windows 浏览器/PG 证据。
- 前置任务：SOL-02 目录身份链通过；SOL-04 章节身份和 SOL-01 参考资格未完成，故本项只做前置核查。
- 模块/实体/API/权限：Solution/Project/Review/Trace；`SolutionOutlineVersion`、`SolutionSection`、`RequirementVersion`、`ReferenceSolutionVersion`；冻结 `SOL_OUTLINE_VERSION_CREATE/GET/LIST/VALIDATE/SUBMIT_REVIEW`；CREATE 须 PM/实施成员，Review 发起须 PM，均需服务器复验。
- 验收标准：列明可复用 Schema、缺失 Owner/来源/Review、实际阻塞、最小施工顺序及迁移/回滚和验证要求；不得以目录身份或 AI 建议代替正式方案版本。
- 风险：只做空 DRAFT 版本会产生表面可用而无法固定章节/需求/参考的伪成果；不可把历史 Reference 读取或空批准指针说成现时合格来源。

## 对账结果

1. 冻结 API-04 要求版本 CREATE 固定有序章节、已批准需求版本、符合资格的参考版本及缺失/冲突声明；VALIDATE、Review 分离。DM-05 明确目录审批不等于章节正文审批，正式输出还须固定 Approved SectionVersion/SpecVersion。
2. 0137 的 `sol_outline_versions`、`sol_outline_sections`、`sol_outline_requirement_refs` 具同项目复合 FK、顺序/去重、计数和 Review 双引用，但三表 `INSERT/UPDATE/DELETE` 均由 `guard_solution_outline_version_foundation()` 拒绝，TRUNCATE 也拒绝。当前没有受权 Owner/公开路由/前端；`sol_outline_reference_refs` 尚未建立。
3. 0136 的 `sol_sections` 仍由身份 Guard 拒绝写入，故无法在真实项目中形成章节身份及稳定顺序。0138 章节 Version 同样保持写保护，不能把章节身份误当批准正文。
4. 当前 `sol_reference_versions` 的 DB 状态约束为 `version_state='DRAFT'`，Reference Revise/Set Eligibility 的完整 Owner/公开链尚未完成；历史 Reference 读取不证明现时资格。需求正式 Approved 事实须由 Requirement Owner/Review 服务复验，单靠外键不足。
5. `ProjectAuthorizationService` 尚无 `SOL_OUTLINE_VERSION_*` 策略；Review/Trace 当前也未接上 OutlineVersion 业务主体。直接解除 DML Guard 或仅创建空 DRAFT 均不能满足冻结来源与追溯合同。

## 施工顺序与边界

按 CR-SOL-002 的分层施工原则，下一项先做 `SOL-04-A01` 章节身份 CREATE 前置核查，再单项实现受权初态 INSERT/快照、HTTP、Windows 组合和浏览器证据；随后并行补齐 SOL-01 Reference Revise/Eligibility 与需求已批准来源证明，才推进 SOL-03 版本固定引用、Owner、VALIDATE、Review/Trace。每个新 DML 解锁先立正式 Change Request，列出迁移、历史拒降、回滚和负例；不改写 0137 原迁移。无新 Schema/代码/API/依赖，此顺序决定可回退，但不能将未具备的来源约束豁免为 PASS。

验证：静态核对冻结 API-04/DM-05、CR-SOL-002、0136～0138/0146 Migration、Solution ORM、Project 策略与现有 Owner。未运行新数据库或浏览器测试；SOL-02-A06-P09-A04 已通过的合成浏览器证据不能替代本项 Version 验收。TraceLink：Gate 2/API-04/DM-05 → CR-SOL-002/0137 → SOL-02-A06-P09-A04 → 本核查 → SOL-04-A01。
