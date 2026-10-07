# REQ-01-A12-A02：多Subject资格集合合同与兼容注册表

日期：2026-10-08。结论：`REQ_01_A12_A02_AGGREGATE_QUALIFICATION_PASS`。下一项：
`REQ-01-A12-A03` Requirement current-fact资格Owner。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A02
输入基线：CR-REQ-004、DEC-1014、既有单Subject资格合同与Handover/Survey Owner
前置任务：REQ-01-A12-A01 PASS
涉及模块：workflow.application.checklist_qualification及纯单元测试
涉及实体：只新增内部Approved Subject聚合投影，不写业务实体
涉及API/权限：无公开API、权限、生产组合或路由变化
验收标准：真实复数Subject/Review保真、稳定顺序/集合指纹、跨项目/重复/漂移拒绝、旧Owner不变
风险：为兼容而保留伪主Subject；乱序集合产生不同Gate；Evidence/Review跨项目混入
```

## 实现结果

- 新增`ChecklistQualificationSubject`，每个成员精确绑定业务Subject、固定Version、内容指纹、非空
  Evidence集合和一个APPROVED ReviewRound；Review的type/id/version/fingerprint必须逐字段匹配。
- 新增`AggregateChecklistQualification`，要求至少一个Subject、规范排序、Subject/Version/Review/Round
  全部唯一且同项目；范围Evidence去重，scope/qualification fingerprint均固定32字节。
- 聚合结果显式提供`subject_version_refs/review_round_refs/evidence_refs`与不含item key的coherence key，
  使Requirement两个Checklist item可以证明同一范围，同时各自保留不同资格内容指纹。
- 注册表返回类型扩展为单Subject或Aggregate两种精确类型；未知对象、Owner异常、错Project/stage/item仍
  统一失败关闭。Handover与Survey继续返回原类型，无字段、序列化或运行行为变化。

## 验证、兼容与回滚

- 新增4项聚合合同测试；与既有registry/Handover adapter/Survey Owner合计15项通过。
- 后端全量3073项通过、3项环境跳过；source/tests `compileall`通过。
- 开发wheel 1165项，SHA-256：
  `cedcb4d52e48b34a68a40e2343206c758da4765f6236969d0ca1ddea07f1eb4e`。
- 无Schema/Migration、公开API、依赖、权限、Secret、客户数据或外发变化；A03前没有聚合Owner注册到
  生产服务。删除新增类型、注册表union和测试即可回滚，现有业务/Workflow历史不变。
- 当前不声称Requirement当前事实、Checklist/Preview/Transition、真实PG/Edge、Gate 3或发行通过。
