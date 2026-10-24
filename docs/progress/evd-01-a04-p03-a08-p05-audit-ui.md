# EVD-01-A04-P03-A08-P05：资格审计回查页面

日期：2026-10-01；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS / REAL_BROWSER_OPEN`。

输入：A08-P03 浏览器会话内未确认操作记录、A08-P04 项目负责人只读审计客户端、冻结 AUDIT_PROJECT_LIST 权限。前置客户端合同通过。范围仅 Evidence 页面与测试；无实体、API、权限、Schema、依赖变化。

同 actor 且当前项目有待核对操作时显示回查区域。项目负责人可主动读取与 actor/Evidence/action/outcome 匹配的资格审计并继续签名分页；CustomerManager 不发审计 GET，仅提示联系项目负责人。页面把事件时间、结果、AuditId、TraceId 明确标为只读线索。无事件时说明默认最近24小时的空结果不能证明请求失败；有事件时说明 Audit 不含本次 Idempotency-Key，不能自动认定本次请求成功。任何结果或网络错误都不清除会话待核对记录、不换 Key、不重发 POST。项目切换和卸载清除页面审计投影，不删除操作记录。

新增2项页面测试；前端全量1,040项、typecheck/build PASS。真实浏览器仍因 A09 computer-use 初始化阻塞，实际 PostgreSQL Audit 回查联动及正式目标账户/HTTPS未验。CustomerManager 独立自助恢复路径、操作号精确核对和人工安全清理待后续设计；不得凭合同测试关闭 Gate3。

兼容/升级：前端增量，无 Migration。回滚移除只读 UI，原服务器 Audit/收据和会话待核对操作不应被删改。
