# SOL-04-A11：Section LIST 内部受权 Owner/keyset

日期：2026-10-09。结果：`SOL_04_A11_SECTION_LIST_OWNER_PASS`，限内部服务、Windows 11 一次性 PostgreSQL 18.6 与合成 License；公开 LIST/cursor/Vault 未实现。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A11。
- 输入基线：冻结 API-04 `SOL_SECTION_LIST`、A10 前置核查、0148 Section 身份、A07 GET 指针复验。
- 前置：Section 创建、同项目 GET/成员读策略及真实 PG 已通过。
- 模块/实体/API/权限：仅 Solution 内部读 Owner/仓储、Project `SOL_SECTION_LIST` 当前项目成员读策略和测试；无 Schema/Migration/公开 API 变化。
- 验收：真实 Session/PG 三页 UUID keyset、不重复不越项目、当前成员/License/暂停/异常指针失败关闭及后端全量。
- 风险：项目全量分页的索引/20 并发性能尚未验证；本项不把内部 keyset 宣称为对外安全 cursor，也不报性能 PASS。

## 实施与验证

在 `SectionReadService` 中新增 `list_current`，每页独立复验 License、Session、当前项目成员；只接受内部 UUID 位置和 1～100 page size。SQL 仓储按 SectionId UUID 升序、`limit+1` 取页，固定 ProjectId 过滤/共享锁，每条复验非空批准指针同 Section/Project、APPROVED 及 Review 双引用，并返回最小摘要。页面结构验证严格单调、不超限、`has_more`/下页位置一致；公开 HTTP 不接收原始 `after_section_id`。

Win11 隔离 PG18.6 真实 Session 验证三条 Section 三页、空尾页、PM/实施成员/客户角色、跨项目/暂停/失效 Session/License 拒绝；一次性库注入损坏指针后 LIST 失败关闭，再恢复触发器/指针。原 PROJECT Reference 与 Section GET 夹具回归通过；后端全量 `3386 passed, 3 skipped, 5108 subtests passed`。20 并发与项目全量索引计划未测；如后续性能不满足，先登记 DB 增量 CR/迁移再优化。

兼容/升级/回滚：无 Migration、依赖、公开 API 或前端变更；移除内部 LIST Owner/策略可回滚，历史 Section 保留。下一项 `SOL-04-A12` Section 独立签名 cursor；随后 Vault/HTTP/Windows。正式目标账户/License、Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
