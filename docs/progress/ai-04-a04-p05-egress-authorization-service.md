# AI-04-A04-P05：Egress Authorize/Revoke 内部应用服务

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-013、DEC-706～710、冻结 `EGRESS_AUTHORIZE/REVOKE`

新增 Project Egress Authorize/Revoke 内部 Application Service 及 PostgreSQL Repository。Authorize 仅允许当前 ProjectManager/CustomerManager，在 License、Session/CSRF、Project 权限和可注入部署批准策略同时通过后，锁定不可变 Preview，核对预览指纹，且只允许缩小数据类别、记录/字节/Token/重试上限和有效期。Authorization Root、Audit、不可变首次结果与 Idempotency Receipt 在同一事务提交。

Revoke 仅允许原批准者或当前 ProjectManager/CustomerManager，以强版本0将状态单向变为 `REVOKED@1`，并原子保存 Audit、撤销事件、首次结果和收据。Authorize 的幂等重放从不可变首次结果投影 `AUTHORIZED@0`，即使权威根之后已撤销，也不把当前 `REVOKED@1` 伪装成原201响应。新操作始终读取当前根并失败关闭。

验证：定向17项 PASS；Win11 隔离 PG18.6 真实验证边界缩小、部署策略拒绝、Authorization/Audit/Result/Receipt 原子性、请求冲突、Audit 回滚、撤销单向状态、历史重放和跨项目隔离 PASS；后端2121运行/3跳过 PASS。验证脚本首轮撤销幂等键仅15字符，被平台正确拒绝；仅将夹具修正为16字符后完整重跑。开发 wheel SHA-256 `2b319bb6b3275317bd489aede16ed2e07041c6fdd41a2b42db4ed1e551afc1cd`。

边界：本项不新增 Schema，复用0068/0069；部署策略只定义强制 Port，正式策略来源与组合待后续发行验收。未实现 Task Owner 投影、HTTP、生产组合或真实外发，Gate 3/UAT/可使用程序包仍未通过。
