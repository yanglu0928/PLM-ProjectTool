# CR-RVW-002：撤回原因历史完整性

日期：2026-09-26；登记 WBS：RVW-02-A06；实施：RVW-02-A07。状态：IMPLEMENTED_SCHEMA_PASS；受权命令及实际 Owner 仍待。

## 来源与证据

冻结 AF-02 `docs/architecture/application-contracts-v1-candidate.md` 的 ReviewService 包含 `withdraw(review_round_ref, reason, command_context)`。当前纯 Domain 可表达 reason；0034 `rvw_round_events` 未存 reason，固定轮次查询构造 Withdrawal 仅用 actor/time。实际受权撤回命令尚未实现。若直接沿用结构会丢失用户输入；不允许把日志或 Audit reason_code 当客户自由文本历史。

## 方案与选择

不选丢弃原因、拼接 event_type 或复用 Decision comment；不选改写 0034。选择独立增量迁移，为 WITHDRAWN 事件增加 nullable withdrawal_reason TEXT，其他事件必须 NULL，提供 ORM/查询、合法文本校验、历史不变与新行完整性测试。沿用可选原因；非空提供时必须实质内容、无 NUL，应用长文本配额按既有规则，不新增冻结 HTTP 必填字段。

旧事件保持 NULL，表示历史未记录，禁止补写 AI 猜测原因。所有已提交事件继续不可变；不得让新列绕过原触发器。数据库实施前复核事件触发器与 migration copy，确保未改变原事件匹配/终态规则。

## 差异与影响

只增加 Review owned 历史字段，不改变全部人完成才汇总、角色、授权、License 或公开 API。保留 64cdf09 与 0034 原版本。原因是客户内容，不进普通运行日志、Git 或脱敏 Audit；本 CR 与测试仅用合成文本。当前内部交接 DTO 已保留原因，但尚不能持久化；正式撤回入口仍不开放。

## 迁移与回滚计划

备份后增量 up；旧 NULL 不回填。验证空库/有数据升级、ORM 一致性、历史读取、不可变和错误事件拒绝。down 在存在非 NULL 原因时拒绝，防止丢失正式历史；仅全 NULL 时可移除新增字段。禁止不可恢复生产操作。程序回滚关闭受权撤回入口而不删除历史。

## 验证计划与未完成项

RVW-02-A07 完成 ORM/0035/查询及空库/有数据 up/down/re-up 验证：旧原因 NULL 和旧字段保留、中文原因读回、空白/非撤回原因拒绝、历史不可变、含原因 down 拒绝 PASS。down 在同事务表排他锁下检查，防止并发新增原因丢失；0034 原文与原不可变触发器保留。详见 `docs/progress/rvw-02-a07-withdrawal-reason.md`。

受权决定/撤回仍需原因幂等重放、不同原因同 Key 冲突、Audit/receipt/Owner 故障全回滚、最终决定/撤回并发测试。Schema 完成不等于实际客户批准或入口开放；无真实 Owner 不挂载 HTTP。
