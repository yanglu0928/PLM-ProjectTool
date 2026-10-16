# SUR-03-A07：Round completeness caller-transaction Owner

日期：2026-10-06。结论：`SUR_03_A07_ROUND_COMPLETENESS_PASS`。下一项：`SUR-02-A06` 接通Round CLOSE与七个Round HTTP。

## 实现

- 新增不自行commit的Round完整性Owner，按稳定顺序锁定OPEN Round、固定target departments、全部Assignment、当前Response/Answer/Evidence；供上层CLOSE在同一事务消费。
- 明确拒绝空Assignment集合；Assignment部门集合必须精确覆盖固定Version全部目标部门，且每条Assignment必须VALIDATED。
- 每条Assignment重新执行A05活动条件、必答、ValidationRule、EvidenceRequired和facilitated来源规则，并经Evidence/Document Owner重证当前资格、DocumentVersion、lock和fingerprint。
- 报告指纹绑定Project/Round/Version、目标部门、Assignment/lock、当前Response及Evidence观测；相同锁定事实生成相同32字节指纹，不包含正文或Secret。

## 验证

- Windows 11/PostgreSQL 18.6：完整单目标Round、稳定重复证明、Round/Assignment/Evidence竞争锁、空Round、非VALIDATED、Evidence撤销漂移及Alembic drift均通过。
- 后端全量`2902 passed / 3 skipped`、`4203`子断言；wheel`1084`项，SHA-256 `05f1aabae62cf01ac90ba00a75d9a31103cceb4a21813e07677bf15b14cb9069`。wheel不是最终交付安装包。

## 兼容与回滚

无Schema/Migration、公开API、依赖、Secret或外发变化；Owner仅返回内部证明且不写业务状态。停止CLOSE组合即可保持旧的失败关闭行为；已存在答复历史不受影响。Round CLOSE/HTTP、Assignment/Response HTTP、Windows组合、UI/浏览器、Gate3/UAT及发行仍待。
