# PRT-01-A06-A03：PrototypeVersion DRAFT Create Owner

日期：2026-10-08。结论：`PRT_01_A06_A03_VERSION_CREATE_PASS`。下一项：
`PRT-01-A06-A04` Version List/Get 与 Validate Report。

## 实施结果

- Migration0131新增不可变`prt_version_create_results`，前向开放四张Version owned表的CREATE Owner；
  Prototype Root行锁串行`version_no/supersedes`，只允许DRAFT且Review为空，完整Artifact/Requirement/
  Interaction/Result由延迟闭包在提交时验证，全部历史拒绝UPDATE/DELETE/TRUNCATE。
- 新增Create Service/Repository与`PRT_VERSION_CREATE`授权。授权和License双检后在同一事务重证Template、
  Requirement和Document证明，写Version/owned集合/结果/Audit/receipt；持久重放重证当前权限与License。
- Artifact与Requirement必须非空、有界、去重并规范排序；Interaction/coverage复用不可执行有界JSON合同。
  OutputArtifact没有Owner时失败关闭；DRAFT创建不更新`current_approved_version_ref`。

## 验证

- Win11/PostgreSQL 18.6：空库0130→0131→0130→0131、drift、DRAFT v1→v2链、owned集合/结果闭包、正式
  指针隔离和有历史拒降PASS；合成数据库已销毁。既有RAG opclass/computed-default drift告警未变化。
- 首次单元测试发现复用Template安全JSON校验会泄漏Template异常类型；已转换为稳定Version
  `VALIDATION_FAILED`并复跑，未放宽安全键/文本限制。
- 定向31项/642 subtests，后端3132项通过、3项跳过、4671 subtests，compileall均PASS。
- wheel共1203项，SHA-256 `4ecd8f05eb01dea276d36813735a653d5081feaf3c63a1b478211a9d516df41d`。

## 兼容与回滚

0131为前向加结果表和Owner触发器，不改公开API/依赖/外发/License。无Version历史可降0130；有历史拒绝
破坏性降级。可停止Service装配，历史Version/引用/交互/Audit/receipt不得删除。Server2025未验证，Debian13
按指令跳过；A04、A07～A11、Gate3/UAT/发行仍待。
