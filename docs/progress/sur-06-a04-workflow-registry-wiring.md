# SUR-06-A04：Workflow qualification registry 生产接线

日期：2026-10-07。结论：`SUR_06_A04_WORKFLOW_REGISTRY_WIRING_PASS`。下一项：`SUR-06-A05`
Windows 11 / PostgreSQL 18.6 真实写链与阶段推进验证。

## 实现结果

- Checklist preview、record 和 Stage Transition 改为仅依赖业务中立的
  `CurrentChecklistQualification` 与显式 registry，不再直接识别 Handover 私有 DTO。
- 注册表明确绑定 Handover 两项和 Survey 两项；未注册 item 、错 Project/stage/item、
  Evidence 集不匹配或 Owner 异常均失败关闭。
- Stage Transition 保留 `HANDOVER → SURVEY`，新增且仅新增
  `SURVEY → REQUIREMENT`；同一事务重证两项并要求相同 subject/version/ReviewRound
  coherence key。Repository 继续负责当前阶段、顺序、Checklist 历史和版本锁。
- qualification HTTP 路径不变：Handover 响应字段及序列化顺序保留；Survey 使用
  `survey_conclusion_id + review_round_ref + evidence_refs` 独立严格变体。
- Windows 生产组合显式装配 Handover adapter 与 Survey Owner，复用现有 Document、
  Evidence、Conclusion current validator、Review 与 Project Manager 授权边界。

## 兼容、迁移与回滚

- 无 Schema/Migration、无新 URL、依赖、Secret、License 或数据外发；Checklist 写请求和
  Handover 响应不变。Survey 仅对原定义的两个 item 开放资格与顺序推进。
- 回滚可移除 Survey 注册和 `REQUIREMENT` target 分支，恢复 Handover-only；已写入的
  Checklist/Transition 历史保留，不重写、不降级。
- 本项是 service/HTTP/composition 合同证明，不宣称真实 PostgreSQL 写链或浏览器通过；
  该证据分别留给 A05 和 A07。

## 验证证据

- Handover/Survey Checklist preview、record、transition、Windows composition 与 HTTP 定向 39 项通过。
- 后端全量 2957 项通过、3 项环境跳过；source/tests `compileall` 通过。
- 开发 wheel 1109 entries，SHA-256：
  `81c9e929673c4a45dd4af858c8253454c4d9873243205a0301641e77e272fa4f`。
