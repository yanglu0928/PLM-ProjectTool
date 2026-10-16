# SUR-03-A06：Assignment VALIDATE/RETURN 与退回重提

日期：2026-10-06。结论：`SUR_03_A06_ASSIGNMENT_REVIEW_PASS`。下一项：`SUR-03-A07` Round completeness caller-transaction Owner。

## 实现

- 新增内部VALIDATE/RETURN Owner；仅ProjectManager、ImplementationMember可操作SUBMITTED Assignment，强ETag、Session/CSRF/License、Audit和持久幂等均在状态事务内完成。
- VALIDATE重新锁定固定问题、当前更正链尾和Evidence，并完整复用A05条件、必答、ValidationRule和Evidence当前性计算；提交后Evidence漂移不能被批准。
- RETURN保存NFKC规范化的1～2000字符人工意见，不删除或覆盖Answer历史。RETURNED只能通过追加同题更正进入IN_PROGRESS，再经SUBMIT重新计算，最后方可VALIDATE。
- 幂等回执返回首次命令状态/ETag，不冒充当前GET状态；重复终态命令使用新Key仍由数据库状态机拒绝。

## 验证

- Windows 11/PostgreSQL 18.6：同Key双线程VALIDATE、RETURN意见、客户越权、CSRF/License、Audit故障全回滚及同Key恢复、RETURNED→更正→SUBMITTED→VALIDATED、终态拒绝、精确状态/Audit计数与Alembic drift均通过。
- 首轮真实验证发现策略误复用仅ProjectManager的`MANAGERS`集合；已改为冻结合同的ProjectManager+ImplementationMember并从全新临时库重跑，未扩大到客户角色。
- 后端全量`2899 passed / 3 skipped`、`4203`子断言；wheel`1082`项，SHA-256 `9d814bab2c14f5551b7db3945184c2e9bd983a7fab904a52b5db3f70c3a594ae`。wheel不是最终交付安装包。

## 兼容与回滚

无Schema/Migration、公开API、依赖、Secret或外发变化；只增加内部状态Owner与两项冻结操作策略。停止后续组合可阻止新命令，已写Assignment状态、意见、Audit、receipt和答复历史保留。A07 Round完整性、Round CLOSE、HTTP/UI/浏览器、Gate3/UAT及发行仍待。
