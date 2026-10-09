# SOL-03-A04-P03-P02-A01：OutlineVersion 固定 Section 身份证明

日期：2026-10-09。结果：`SOL_03_A04_P03_P02_A01_SECTION_USE_PROOF_PASS`；仅内部稳定章节身份，目录版本写仍关闭。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P03-P02-A01。
- 输入基线/前置：Gate2 DM-05/API-04、CR-SOL-002、已验证 SOL-04 受控 Section 身份创建/读取和 P03-P01 创建授权策略。
- 单一问题：固定有序章节引用时，确认 Section 仍为当前同项目、同 Outline 的 ACTIVE 稳定身份，并持锁防止并发状态变化。
- 模块/实体/API/权限：Solution Application 内部最小证明，复用 Solution 自有 `SqlAlchemySectionReadRepository.get_current` 共享锁；无 Schema/Migration、公开 API 或角色变化。调用者必须先通过 Owner 授权；本服务本身不是公开读取接口。
- 验收：有效但尚无批准正文的 Section 可固定身份；跨项目、错 Outline、归档、端口故障失败关闭；真实 PG 行锁与全量回归。风险：这不是 SectionVersion 正式化或内容批准证明，后续 VALIDATE/Review 必须另验。

## 实施与验证

`OutlineSectionUseProofService` 仅返回 ProjectId/OutlineId/SectionId，检查只由本模块读端口提供的当前身份、父目录与 ACTIVE 状态。定向 3 项/5 子例通过；Win11 临时 PG18.6 真实 Section 创建后，正例、跨项目、错目录、归档及 `FOR UPDATE NOWAIT` 锁验证退出 0。后端全量 3432 通过/3 跳过/5239 子例，保留既有 2 条告警。

兼容/回滚：无数据库/API/依赖变化；未接线证明可撤，保持 OutlineVersion 写 Guard 关闭，历史数据不动。下一项 `SOL-03-A04-P03-P02-A02` 建立 Requirement 自有的当前已批准 RequirementVersion 证明接口；再组合 Owner 原子写。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/016 → SOL-04 Section 身份 → 本固定身份端口 → OutlineVersion Owner。
