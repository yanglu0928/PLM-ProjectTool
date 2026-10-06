# SUR-03-A03：Assignment create/list/get 与动态可见性 Owner

日期：2026-10-06。结论：`SUR_03_A03_ASSIGNMENT_OWNER_PASS`。下一项：`SUR-03-A04` Response/Answer/Evidence 追加与 FACILITATED_RECORD 同事务来源固定。

## 实现

- 新增 Assignment 原子创建：ProjectManager/ImplementationMember 经 Session、CSRF、License、Project授权、OPEN Round、固定target department、当前有效assignee、持久幂等和Audit后创建ASSIGNED事实。
- 新增稳定列表/详情：PM/ImplementationMember查看全Round；显式assignee仅本人可见；部门级Assignment仅该部门当前有效成员可见。每次读取重新验证Session、项目成员和部门，不依赖创建时快照。
- 新增按`(created_at, assignment_id)`倒序的稳定分页和绑定Session/Project/Round/page-size/复合位置的独立cursor；详情当前只投影Assignment及response_count，不提前复制答复正文。
- 创建首次结果严格校验实际Assignment ID并与receipt一致；仓储异常对象不能被误收为成功回执。

## 验证

- Windows 11/PostgreSQL 18.6：PM/Implementation创建、Customer拒绝、非法target、同Key并发收敛、Audit故障整笔回滚及同Key恢复、四条Assignment稳定分页、PM全量、显式assignee/部门级可见性、他人详情隐藏、成员停用立即撤权、License与drift均通过。
- 后端全量`2884 passed / 3 skipped`、`4167`子断言；wheel`1074`项，SHA-256 `ce26a7b545fc252a5e81cad0bc856110ba2deb68abb078f64ac53cbaf6b74dee`。wheel不是最终交付安装包。

## 兼容与回滚

无Schema/Migration、公开URL/JSON、依赖、Secret或外发变化；只增加内部Owner、三项冻结策略和cursor。未装配Router时外部仍404；停止后续装配可阻止新写，已有Assignment/Audit/receipt历史保留。
