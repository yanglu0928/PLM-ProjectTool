# SOL-03-A04-P03-P03-P03：OutlineVersion 当前输入证明组合

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P03_OUTLINE_INPUT_PROOF_PASS`；仅内部同事务证明与服务端内容指纹，版本写 Guard/HTTP 仍关闭。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P03-P03-P03。
- 输入基线/前置：Gate2 DM-05/API-04、CR-SOL-002/016/017、DEC-1141；已验 DRAFT 输入合同、Section/Requirement/Reference 现时证明及 Outline 根身份。
- 单一问题：在调用者同一事务内锁定 ACTIVE Outline 和最新版本链，并逐一重证有序 Section、当前已批准 RequirementVersion、PROJECT/GLOBAL 当前 ELIGIBLE ReferenceVersion 的真实来源及确认，生成不由客户端提供的内容指纹。
- 模块/实体/API/权限：Solution Application 内部组合与自有 Root/Version 只读仓储，Requirement 跨模块仅 Application Interface；无新 ORM/Schema/Migration、公开 API/角色/依赖。实际用户授权、License、收据与 Audit 由后续 Owner 实施，本接口不得直接暴露。
- 验收：双 Scope 合成真实 PG/文件正例、跨项目、文件篡改、资格限制、GLOBAL 确认到期、Root 锁；定向/全量。风险：首响/写 Guard 未开放，现时证明必须保持到实际写事务提交，不能在 API 预查后另开事务复用。

## 实施与验证

`SqlAlchemyCurrentOutlineVersionBase` 独占锁定同项目 ACTIVE Outline，校验批准指针，再读取最新版本链并返回下一个版本号/前驱；`OutlineVersionInputProofService` 调用 Section、Requirement、Reference 各自现时证明。服务端内容指纹规范绑定项目/目录、版本号/前驱、有序章节、需求摘要与 Review 身份、参考来源摘要/资格事件/确认身份及声明；输入请求指纹与内容指纹分列，任一端口不一致失败关闭。输出不含正文、Locator、GLOBAL 管理员会话或存储路径。

定向 4 项通过；Win11 两套隔离 PG18.6 中，PROJECT 使用真实受权创建的 Outline/Section/Reference 与合成已批准 Requirement，GLOBAL 目标项目/Section/Requirement 为测试合成身份，Reference/确认/Document/Evidence 为真实夹具；双 Scope 证明、跨项目、物理篡改、RESTRICTED、确认到期、Outline 根 `FOR UPDATE NOWAIT` 锁验证退出 0。GLOBAL 合成目标项目不等于最终项目成员 HTTP 授权验收；后端全量 3446 通过/3 跳过/5256 子例，保留既有 2 条告警。

兼容/回滚：无 DB/API/依赖变化；移除未接线的内部服务即可回滚，0155 和旧 Guard 保持关闭。下一项 `SOL-03-A04-P03-P03-P04` 实施 INSERT-only SQL Guard、固定集合/首响闭合及 Owner 同事务授权/License/收据/Audit；再作真实双 Scope、权限/并发/回滚和 HTTP/Windows 验收。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/016/017 → Section/Requirement/Reference 现时端口 → 本组合 → OutlineVersion Owner/Guard。
