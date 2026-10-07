# SUR-06-A03：Survey Workflow current-fact Owner

日期：2026-10-07。结论：`SUR_06_A03_SURVEY_WORKFLOW_OWNER_PASS`。下一项：`SUR-06-A04`
Workflow Checklist/preview/transition 与 Windows 组合接线。

## 实现结果

- 新增 Survey-owned policy、current-fact Owner 与 PostgreSQL Repository；Repository 只在项目内恰有一个
  ACTIVE Survey 的 APPROVED Conclusion 时返回并锁定聚合，零个或多个候选均失败关闭。
- 两个 item 都复用 `SurveyConclusionCurrentValidator` 重证 CLOSED Round、VALIDATED 链尾 Response、
  PROJECT_RECORD、HND open issue 与 AI provenance；任何当前 issue 都拒绝资格。
- Owner 进一步固定 Response 的 Answer Evidence 快照并通过 Evidence Owner 重证当前 Project 授权、
  固定 DocumentVersion、锁版本、内容指纹和非 TEMPLATE 类别；Conclusion SUPPORT Evidence 与答复
  Evidence 合并、去重后作为 Workflow basis 候选。
- APPROVED Review 必须精确匹配 `SRV-05 + conclusion_series_id + survey_conclusion_id +
  SURVEY_CONCLUSION_ALL_V1`，且 Review subject fingerprint 与 Conclusion content fingerprint 一致。
  两项生成不同资格指纹，但共享同一 subject/version/Review coherence key。
- `ConclusionResponseProof` 兼容增加结构化 Evidence 快照；原 `evidence_ids` 保留，既有构造调用因默认值
  不受破坏，真实 Repository 同时返回两者并由 Owner 要求精确一致。

## 兼容、迁移与回滚

- 无 Schema/Migration、公开 API、角色、依赖、Secret、License 或数据外发变化；A04 前不注入生产
  Workflow 服务，现有 Handover/Survey HTTP 行为不变。
- 删除新 Owner/Repository、Response Evidence 扩展和专项测试即可回滚；业务与 Workflow 历史不改写。
- PostgreSQL Repository 真实锁序、Checklist 写入、Stage Transition 和浏览器闭环留 A04～A07，
  本项不将单元证明描述为数据库或 Gate 通过。

## 验证证据

- 新增专项 5 项通过；SurveyConclusion 既有 28 项、通用 registry/Handover adapter 6 项回归通过。
- 后端全量 2953 项通过、3 项环境跳过；Survey application/infrastructure `compileall` 通过。
- 开发 wheel 1109 entries，SHA-256：
  `1fd65b1f664f193ecbd8f7c4f8b0eeca157bcf3b262c83255d203896368508be`。
