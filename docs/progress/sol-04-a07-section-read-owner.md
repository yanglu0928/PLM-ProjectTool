# SOL-04-A07：Section 当前详情内部只读 Owner

日期：2026-10-09。结果：`SOL_04_A07_SECTION_READ_OWNER_PASS`，限内部服务、Windows 11 一次性 PostgreSQL 18.6、真实 Session/合成 License；公开 GET、Windows 组合与 UI 未实现。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A07。
- 输入基线：冻结 API-04 `SOL_SECTION_GET`、DM-05、0148 Section 身份、A06 只读链前置核查及 Outline GET 读模式。
- 前置：Section 创建/Guard/首次结果、同项目身份约束、读取风险分析已通过。
- 模块/实体/API/权限：仅 Solution 内部当前详情 Owner/仓储和 Project `SOL_SECTION_GET` 读策略；无实体/Schema/Migration/公开 API 变化。所有当前 Project member 可读，锁当前成员事实；无成员、暂停、跨项目隐藏。
- 验收：真实 Session/PG 读取同项目初态；PM/实施成员/客户成员、跨项目/不存在/暂停/失效 Session/License、归档项目/章节、损坏批准指针、后端全量回归。
- 风险：身份或批准指针误当正式方案。仓储复验非空版本同 Section/Project、APPROVED、ReviewRef/ReviewRoundRef；当前未装版本 Owner，不以空指针推断批准。

## 实施与验证

新增内部 `SectionReadService` 和 `SqlAlchemySectionReadRepository`。服务先复验 License、真实 Session、当前项目成员策略，再按 ProjectId+SectionId 读取身份；仓储对根行共享锁并左连接批准版本。若指针非空但版本缺失、跨 Section/Project、非 APPROVED 或缺 Review 引用，则失败关闭为内部不可用；不披露错误详情。返回最小身份/状态/批准指针/创建信息/强 ETag，不读取 SectionVersion 正文。

Windows 11 隔离 PostgreSQL 18.6 中验证 PM、实施成员和客户角色读取，跨项目/不存在/暂停成员/失效 Session/License 拒绝、归档项目及归档 Section 可读。使用一次性数据库短暂禁用表触发器注入损坏指针，验证失败关闭后恢复初态与触发器；此操作绝不用于生产库。原 PROJECT Reference 夹具回归通过；后端全量 `3386 passed, 3 skipped, 5104 subtests passed`。公开 HTTP、正式目标账户、Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。

兼容/升级/回滚：无 Migration、依赖、公开 API 或前端变更；移除新内部读 Owner/策略可回滚，历史 Section 保留。下一项 `SOL-04-A08` 可选 GET HTTP 与真实 ASGI/PG。
