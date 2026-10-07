# SUR-06-A05：Survey Workflow Windows 11/PostgreSQL 18.6 真实验证

日期：2026-10-07。结论：`SUR_06_A05_WORKFLOW_PG_PASS`。下一项：`SUR-06-A06`
前端双阶段资格、记录和推进支持。

## 真实验收结果

- 在 Windows 11 本机 PostgreSQL 18.6 临时库上升级至当前 head，复用真实
  SurveyConclusion Review 链生成唯一 APPROVED Conclusion，然后以生产 Windows 组合
  注入 qualification preview、Checklist record 和 Stage Transition Router。
- 两个 Survey item 的资格在同一事务内返回同一 Conclusion/Review coherence；
  竞争连接对 Conclusion、Evidence 和 ReviewRound 的 `FOR UPDATE NOWAIT` 均收到
  PostgreSQL `55P03`，证明当前事实锁在调用者事务内保持。
- preview 后将 Evidence 改为 INELIGIBLE，record 失败关闭；两个 item 用相同
  `If-Match v4` 并发写入时结果为一个 200、一个 409，失败项用 v5 重试后成功，
  最终只有两条 PASS 历史。
- 两项 PASS 后再将 Evidence 漂移，`SURVEY → REQUIREMENT` 仍返回
  `WORKFLOW_GATE_NOT_SATISFIED`，证明不只信任历史 PASS。恢复原快照后推进成功，
  同幂等 key 重放返回同一结果。
- 最终数据为 current stage `REQUIREMENT` / workflow lock v7、2 Checklist PASS、1 Transition、
  2 gate item、2 Checklist Audit、1 Transition Audit；两次独立执行均 PASS 且临时库已删除。

## 偏差、迁移与回滚

- A05 为隔离 Survey 写链验证，fixture 从合法的 ACTIVE Survey 阶段开始；它不冒充
  `HANDOVER → SURVEY` 全链或浏览器验收。完整前两阶段 Edge 流程保留给 A07。
- 无产品 Schema/Migration/API/依赖/Secret/License/外发变化。为复用正式批准结论夹具，
  仅给旧验证入口增加可选 callback；默认调用和旧 PASS 输出不变。
- 删除 A05 验证脚本并撤回可选 callback 即可回滚；产品历史与数据库不受影响。

## 验证证据

- A05 真实 PG/HTTP 脚本连续独立执行 2 次，均为 PASS；Alembic `check`无新迁移。
- 后端全量 2957 项通过、3 项环境跳过；新旧验证脚本 `compileall` 通过。
- 开发 wheel 1109 entries，SHA-256：
  `47597ce45525b7c8706b7c8606c55607191944e93166e7c93bab78e5ad8e2fe0`。
