# CR-PLAN-007：PlanVersion Review生命周期状态保护

日期：2026-10-26。状态：`0190_SCHEMA_GUARD_IMPLEMENTED_AND_WIN11_PG18_VERIFIED_OWNER_INTEGRATION_PENDING`；按用户持续自主执行授权登记，本CR及Gate均非用户确认/通过结论。

## 发现与影响

Gate 2冻结PlanVersion模型含version_state、review_ref和review_round_ref，冻结API-04要求固定版本经统一Review送审及后续批准/退回。但Migration 0188将PlanVersion根表所有UPDATE均拒绝；因此即使统一Review创建了Review/ReviewRound，PlanVersion也无法原子绑定Review或推进状态，后续读取/Review资格会失实。不能绕过触发器直接写入，也不能把Review事实只放在Audit摘要或依赖缓存。

## 方案比较与决定

- A：弱化/删除0188 append-only guard并允许任意更新。拒绝：会重新开放内容快照、固定来源/WBS及历史身份的篡改风险。
- B：新增一张Plan Review状态投影/表，但不更新既有PlanVersion状态列；要求每个消费者改读投影，冻结模型的ReviewRefs/状态字段成为陈旧值。拒绝：跨模块行为范围更大且造成两套状态来源。
- C（选择）：追加migration 0190，继续拒绝PlanVersion内容列任何改变，但只允许数据库校验过的Review生命周期字段跃迁；并新增Plan-owned append-only生命周期结果表，每次跃迁必须原子写事件，约束它与相同Project/Plan/PlanVersion/Review/Round/Actor及实际统一Review事实匹配。Downgrade遇事件历史则拒绝。

允许的最小根状态跃迁沿用既有模型：DRAFT(null Review)→IN_REVIEW(固定Review+Round)，IN_REVIEW→APPROVED/RETURNED（同Review+Round），APPROVED→SUPERSEDED（同Review+Round）。其它字段不可变，跨Plan/Project/Version绑定、无Review历史或不匹配状态都失败关闭。未来如实现撤回/取消或其它状态，需要独立验证和记录，0190不预授权新跃迁。

## 变更边界

- 只增加Plan模块Review生命周期不可变事件表、索引/FK/检查约束、状态更新guard和Deferred闭合trigger；Gate 2原冻结Schema V1/commit 64cdf09不改写。
- 不改变冻结HTTP路径/ReviewEnvelope/角色/License机制，不将Review决定自动生成；提交/批准由后续真实Review Owner与指定Reviewer操作。
- 依赖同一事务：创建/启动统一Review、计划状态与事件、Audit、Receipt；Review事件须绑定通用Review内的真实Round和该固定PlanVersion。
- 关闭默认/登录/只读路由；无客户数据迁移、无外发、无新增第三方依赖。

## 升级、回滚与验证

- 0190在当前0189之后追加；先在Win11隔离PG18验证空库升迁/drift/降迁重升、事件INSERT身份校验、UPDATE/DELETE/TRUNCATE拒绝、有状态历史降级拒绝、允许与拒绝的Review转换及事务失败原子性。
- Downgrade在存在任何事件或非DRAFT/Review refs历史时停止，不删除事实；只允许无状态历史的空结构回退。
- 遇0188以外新的状态触发器依赖/权限条件不匹配时先暂停该WBS，新增CR/分析，不绕过。
- 风险：任何错误宽松的trigger会使冻结PlanVersion内容可变或Review指针不一致；以数据库直接更新负例和完整实际Review事务证明为必要门槛。

## 授权与追溯

该偏差相对于0188的“全部更新拒绝”约束；本CR先于0190 Schema/Owner编码记录。依用户已批准的持续自主执行授权，可在保留历史、兼容分析与隔离验收后实施，无需逐项再确认。失败时保留原迁移并回滚未部署的0190；不得修改/删除0188或原冻结提交。
