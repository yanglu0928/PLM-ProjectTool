# EVD-01-A04-P03-A08-P04：资格审计只读回查客户端

日期：2026-10-01；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS / UI_AND_REAL_BROWSER_OPEN`。

## 编码前检查

输入：冻结 AUDIT_PROJECT_LIST、A08-P03 会话内待核对操作、AUD-02-A05 Windows 显式组合。前置项目 Audit GET 已限 ProjectManager，CustomerManager 无读取权。本项仅 Evidence 前端只读客户端与测试，不改后端角色、API、Schema、依赖或客户事实。

客户端仅为当前 Session 的 ProjectManager 构造项目 Audit GET，并固定 action=`EVIDENCE_ELIGIBILITY_SET`、outcome=`SUCCESS`、actor_id、Evidence 对象类型/ID；使用同源 Cookie、no-store、签名 cursor 分页。响应严格检查项目、操作者、Evidence、事件结果/前后状态、TraceId、页结构与重复事件，畸形/跨 Scope 失败关闭。只投影事件 ID、时间、TraceId、结果，不携带敏感正文或未审计推断。

4 项定向测试覆盖当前身份过滤、签名游标、CustomerManager 本地拒绝、跨项目/对象/畸形/重复/权限错误；前端全量 1,038 项、typecheck/build PASS。本轮没有 UI 接线、真实浏览器或数据库审计链的新验收。Audit 列表没有 Idempotency-Key，查到事件也不能单独证明某个未确认操作号提交成功；24 小时默认窗口内无事件也不能证明未提交。不得自动清除待核对记录或重发资格命令。

兼容/升级：纯前端增量，无 Migration。后续 UI 只向项目负责人显示受权审计结果；CustomerManager 须通过合规独立恢复路径或项目负责人协助，不据此扩大 AUDIT_PROJECT_LIST 权限。正式目标账户/HTTPS、真实浏览器、Gate 3 仍开放。
