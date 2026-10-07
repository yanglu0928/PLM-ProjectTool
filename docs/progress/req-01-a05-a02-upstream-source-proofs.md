# REQ-01-A05-A02：SurveyConclusion 与 Handover 固定来源证明

日期：2026-10-07。结论：`REQ_01_A05_A02_UPSTREAM_SOURCE_PROOFS_PASS`。下一项：
`REQ-01-A05-A03` PROJECT Evidence 与 Capability 固定来源证明。

## 实现与边界

- Survey 模块新增 Requirement 专用最小 proof：只接受同项目 `APPROVED` Conclusion，并把其
  `conclusion_series_id / survey_conclusion_id / content_fingerprint` 与
  `SRV-05 / SURVEY_CONCLUSION_ALL_V1` 的 APPROVED Review、Round及Review Snapshot精确绑定。
- Handover 模块新增 Requirement 专用最小 proof：只接受同项目 ACTIVE Analysis当前指针精确指向的
  APPROVED Version，并把 Analysis/Version/指纹与 `HND-02 / HANDOVER_ALL_V1` 的 APPROVED Review、
  Round及Review Snapshot精确绑定。
- 两个 adapter 都在调用方已有事务内对全部业务与Review事实取共享行锁，返回类型化最小身份和32字节
  指纹；不返回正文、路径、locator、评论、用户Token或Secret，不自行commit，也不写业务数据。
- 精确Source形状保持A04约束：Survey只保存Conclusion ID；Handover保存Analysis ID与固定Version ID。
  不按时间选择latest，不把单个Handover Item状态、通用Review状态或错配Snapshot当成正式来源。

## 验证

- Windows 11 / PostgreSQL 18.6：同项目Survey与Handover正式终态proof、跨项目、错Version、Review
  Snapshot指纹漂移、Handover Root受限及proof零写均通过；Alembic drift无新增操作。
- 定向16项、后端全量2986项通过且3项既有环境跳过；开发wheel共1131项，SHA-256
  `e79903efb3c3b083b8139d4158415ce261ce4b7042a7f738969e70a2cfb57cd7`，不是正式发行包。

无Schema、Migration、公开API、依赖、Secret、客户数据或外发变化；A03/A04、A06～A12、Gate3/UAT/
发行仍待完成。
