# SUR-04-A06：SurveyConclusion Review Subject 与终态消费

日期：2026-10-07。结论：`SUR_04_A06_CONCLUSION_REVIEW_PASS`。下一项：`SUR-05` 按冻结五个
Operation 接入 HTTP、Windows 显式组合和前端 Evidence/open issue 定位。

## 编码前检查与偏差

- 复用唯一 PROJECT Review kernel，Subject 固定为 `SRV-05`、稳定 `conclusion_series_id` 和
  `SURVEY_CONCLUSION_ALL_V1`；不新增 Survey 专用 Review URL。
- 送审人限 ProjectManager；Reviewer 为当前 ACTIVE Project 的合格成员。只有 latest DRAFT 可送审，
  同 series 同时最多一个 IN_REVIEW，批准时只取代同 series 旧批准版本。
- 当前来源复验证明需要本次会话令牌，但 Review kernel 原来只传 actor。按 CR-SUR-010 增加不可持久化、
  `repr`/比较排除的临时 proof context；token 不进入数据库、Audit、receipt 或响应。
- PostgreSQL 18 实测发现 Migration0109 的整表 UPDATE 禁止与冻结 Review 状态机冲突。按 CR-SUR-011
  新增 Migration0110，只放行 DRAFT→IN_REVIEW、IN_REVIEW→APPROVED/RETURNED、旧 APPROVED→
  SUPERSEDED，并逐字段保持结论业务载荷不可变。

## 实现

- 新增 SRV-05 Subject Owner、PostgreSQL 仓储和原子送审服务；创建 Review、首轮、Subject 绑定、Audit、
  幂等 receipt 在单一事务完成，故 Audit/Subject 失败不会留下半成品。
- 送审和 APPROVE 都重新执行 A05 当前事实验证。RETURN/WITHDRAW 不要求来源继续有效，以允许撤回失效
  评审；两者均将当前版本投影为 RETURNED，修订须另建不可变后继版本。
- APPROVE 原子地把旧 APPROVED 置为 SUPERSEDED，再批准当前版本；Review 终态后 subject lock 释放。
- PROJECT_RECORD 创建 proof 默认仍限项目经理/实施成员；Review 专用实例显式允许全部合格项目成员
  重证其有权评审的证据，创建权限没有扩大。

## 验证

- 定向 35 项通过；后端全量 `2938 passed / 3 skipped`。
- Windows 11 / PostgreSQL 18.6：Audit 故障整笔回滚、送审同键重放、Round 失效时批准失败关闭、恢复后
  批准、第二版退回、第三版批准并替换第一版、终态锁释放、三条业务 Audit、token 零泄漏均通过。
- Migration0110 在有数据数据库完成 downgrade 至0109、旧保护恢复、upgrade 至head、Alembic drift；
  非法载荷更新与非法状态跃迁均被数据库拒绝。临时数据库已删除。
- `compileall` 与开发 wheel 内容检查通过；wheel 1104 项，SHA-256
  `f65b9beddab1f9879de23f2f5abea716bb4c89286eafad95c9357baa588be336`。它不是最终发行程序包。

已知未完成：SUR-05 HTTP/Windows组合/UI、SUR-06 Workflow资格与完整模拟项目、Windows Server 2025、
Gate 3、UAT 和正式发行包。
