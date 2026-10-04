# EVD-01-A04-P03-A03：Evidence 首次资格同事务命令

日期：2026-10-01；Phase 2 Platform Core；结论：`INTERNAL_COMMAND_PASS / POSTGRESQL_AND_HTTP_OPEN`。

编码前输入：冻结 `EVIDENCE_SET_ELIGIBILITY` S/L/C/I/M/A、DM-03 模板规则、CR-EVD-003、Document 来源事实 Port、Evidence 资格角色/锁定 Port、Audit 与幂等收据。前置的内部代码已通过；实际隔离PG18环境当前未运行。范围仅 Evidence 应用命令，尚不挂 HTTP，不产生正式客户事实。

命令先校验人工请求、License 与 Idempotency-Key；调用方事务内复验当前 Session/CSRF/项目角色，锁定指定 scope/project 的 Evidence，再通过 Document 模块同事务复验固定版本/当前类别。模板不能升 ELIGIBLE。首次裁定检查预期 lock_version 与当前 CANDIDATE，条件更新资格、理由、操作人和版本，随后同事务追加 AuditEvent、完成幂等收据并提交。相同 Key/内容只在现有行仍与原结果完全匹配时返回一次结果；不同内容冲突，不静默重裁。若来源撤销、角色失效或审计失败，不返回成功。

本项还收紧资格访问层：命令 token/CSRF 必须与访问对象绑定的 token/CSRF 完全一致；回放不允许用不同凭据借用该对象。后续 HTTP 仍须实施 Host/CSRF/If-Match 解析及错误映射，不能直接暴露内部命令。

验证：命令定向5项及现有访问/持久层定向测试通过；后端全量1793项通过、3项跳过；wheel构建通过。实际 PostgreSQL 行锁/事务回滚/幂等触发器与 HTTP、Windows Server 2025/Debian 均未验；Gate 3 不变。回滚为不挂公开路由并撤内部命令；若以后已有正式裁定，只读保留审计与收据，不能自动删除。
