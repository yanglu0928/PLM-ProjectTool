# CR-WFL-009：Transition Gate Snapshot HTTP 兼容投影

- 日期：2026-10-06
- 状态：IMPLEMENTED / VERIFIED
- 触发 WBS：`WFL-02-A02-A04`
- 关联：冻结 API-02 `WORKFLOW_TRANSITION` / `StageTransitionRequest`、DEC-904～906、CR-WFL-003/004/006～008

## 偏差与原因

冻结`StageTransitionRequest`只列出`target_stage_key`、`reason`和
`gate_snapshot_refs`，没有定义后者的元素类型、身份来源、顺序、Scope或校验语义。
现有可信Gate实际由服务端在同一事务重证Handover Owner并与两个当前Checklist
Record精确核对；客户端没有稳定读取两个当前Record身份的冻结接口。若猜造嵌套DTO、
相信客户端Evidence/Review UUID或要求用户手填，会扩大/破坏冻结合同并把历史引用误作
当前授权证明。

## 采用方案

- 保留冻结POST路径、三个请求字段和200语义；V1请求必须精确包含三字段。
- `gate_snapshot_refs`在当前首批实现中定义为**必须存在且为空的JSON数组**，表示客户端不
  声明可信Gate快照，由服务端选择并固定当前两项Record/Owner观测。非空、非数组或未知
  字段失败关闭，不静默忽略。
- 服务器仍按Baseline→Issues固定顺序重证Owner；响应只返回不可变TransitionRef、来源/
  目标、发生版本/时间及当前Workflow ETag，不返回内部摘要、锁、路径、正文或AI内容。
- 仅`HANDOVER -> SURVEY`已注册；目标以外请求由业务Service拒绝。后续若有真实客户需要
  提交显式快照身份，另开API Change Request并保持空数组客户端兼容。

## 兼容、迁移与回滚

- 这是对冻结但未细化字段的保守兼容解释，不删除/重命名字段，不改变路径、角色、控制或
  状态码；原冻结提交`64cdf09`不改写。
- 无Schema/Migration、依赖、Secret、外发或客户数据变化。Router显式注入，默认应用继续
  404；回滚为停止注入，A03内部命令与历史保留。
- 风险：空数组语义需在前端固定编码；通过严格合同测试和版本说明公开，不把空值解释为
  Gate已省略或未验证。

## 验证计划

- 严格Host/Origin、Session/CSRF、Idempotency-Key、If-Match、唯一JSON键、UTF-8、大小和
  exact-field测试；非空`gate_snapshot_refs`与未知目标拒绝。
- 错误安全映射、最小白名单响应、ETag/no-store、默认404、原键重放合同测试。
- 后端全量、wheel；真实Windows生产组合/PG和前端/浏览器为后续独立WBS。

实施结果：A04已新增显式注入Router、应用装配插槽及冻结错误注册；默认应用保持404。
合同4项、后端全量2777项通过/3项条件跳过；开发wheel 1013项，SHA-256
`84694eb7f938d3b597dd909a612bff6062a617c6e8559fc12b7c817f5facf158`。真实Windows
组合/PG留A05，前端与浏览器留后续独立任务。
