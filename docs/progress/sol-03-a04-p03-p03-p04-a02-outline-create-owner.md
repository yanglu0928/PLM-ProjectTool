# SOL-03-A04-P03-P03-P04-A02：OutlineVersion CREATE 内部 Owner

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P04_A02_OUTLINE_CREATE_OWNER_PG_PASS`；仅内部服务与 Win11 合成 PG 链，公开 HTTP/Windows/UI 未接线。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本任务。输入：Gate2 API-04/DM-05、CR-SOL-002/016/017、DEC-1141、已验项目角色策略、Section/Requirement/Reference 现时证明、0156 INSERT-only Guard。
- 单一问题：把授权、License、幂等、现时输入证明、固定集合/首响、Audit 放在同一 Owner 事务，重放必须读取不可变首次结果而非可变版本状态。
- 范围：Solution Application/Infrastructure 内部服务；无新 DB/Migration、公开 API、角色或依赖变化。无 AI 外发或客户数据。
- 验收：合法首创/版本链、同键重放与变更冲突、非授权/跨项目/License 拒绝、并发同键、Audit 故障整笔回滚、真实 PG 表计数与后端全量。风险：本项 PG 正例使用合成 Outline/Section 身份与显式缺失声明；双 Scope 固定 Reference/Requirement 完整 Owner 写链须独立验证。

## 实施与验证

`OutlineVersionCreateService` 先验证规范输入/Key、License、Session/CSRF 与本项目角色；在同一 UoW 预留按操作和请求指纹绑定的幂等收据。已完成的同键请求只读取 `0155` 不可变首响，不重新创建或追加 Audit。首次请求调用 `OutlineVersionInputProofService` 锁当前 Outline 和来源，随后 `SqlAlchemyOutlineVersionCreateRepository` 顺序写版本、固定 Section/Requirement/Reference 关联及首响，再追加单个 `SOL_OUTLINE_VERSION_CREATED` Audit、完成收据并提交。所有写入受 `0156` 延迟闭合 Guard 约束；异常不提交。

单元 5 项/4 子例通过；Win11 一次性 PG18.6 真实 Auth/项目成员/Section/收据/Audit 链验证：PM/IM 连续 v1→v2、原键重放、变更同键冲突、客户/跨项目/License 拒绝、并发同键仅新建 v3 一次、Audit 故障零额外版本/首响/收据/Audit。旧 Reference 来源夹具回归退出 0；后端全量 3451 通过/3 跳过/5260 子例。真实 Requirement 和 PROJECT/GLOBAL Reference 输入证明已在前项分别验证，但本项未把这些固定引用与 Owner 写链合并运行，故不得宣称全范围 CREATE 验收。

兼容/回滚：无 Schema/API 变更；内部 Owner 尚未对外接线，可撤服务与适配器，保留 0156 及已有历史；若真实写入后不得删历史/逆向降级，应保持入口关闭并前向修复。下一项双 Scope PG 组合、HTTP/Windows、UI/浏览器；Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/016/017 → DEC-1141 → 0155/0156 → 本 Owner → 双 Scope/API 验收。
