# EVD-01-A04-P02：Evidence 首次资格裁定策略

日期：2026-10-01；Phase 2 Platform Core；结论：`DOMAIN_POLICY_PASS / COMMAND_OPEN`。

输入：冻结 DM-03/API-02、CR-EVD-003、Document 来源事实内部 Port。前置：Port 代码已通过，隔离 PostgreSQL 实证尚开放。范围仅 Evidence 领域策略，不挂资格路由、不写数据库、不代替人工确认。

策略仅接收当前 CANDIDATE、受权人工请求的 ELIGIBLE/INELIGIBLE、非空规范化理由和已知来源类别。模板升 ELIGIBLE 失败关闭；模板可判 INELIGIBLE；已有终态不能覆盖。策略返回候选决策，后续命令必须同事务取得 Document 来源事实、验证当前 Session/CSRF/角色、锁定 Evidence、审计与幂等。当前无正式业务事实产生。

验收：新增3项策略测试；后端全量1782项通过、3项跳过；wheel构建通过。未执行实际 PostgreSQL 资格事务或 HTTP 验证，不宣称资格功能/Gate3/程序包可用。回滚可撤策略函数，历史无变化。
