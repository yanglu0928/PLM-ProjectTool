# SUR-07-A06：调研固定来源与版本创建前端客户端

日期：2026-10-25；状态：`FRONTEND_CLIENT_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A06`；只完成只读交接来源候选客户端和冻结 SurveyVersion Create 传输合同。|
|输入/前置|`CR-SUR-013`、A05 新 GET Windows/PG 已验；冻结 SurveyVersion POST、现有 Session CSRF/If-Match/幂等桥已存在。|
|模块/实体/API|Frontend Survey API 与 Session 私有 POST 白名单；无后端/Schema 新改动。|
|权限|客户端预筛项目 PM/实施成员，但不能替代服务端逐页读取与写事务来源重证。|
|验收|字段/来源四类互斥形状、角色/项目、分页签名格式、完整问题快照、目标部门、强 ETag、原操作号、严格201回执/未知结果；定向及全量前端回归和 build。|
|风险|来源候选/AI 建议不等于客户访谈事实；手工来源明确 `MANUAL` 注释，不伪造固定 Handover 引用。|

新增 `SurveyHandoverSourceClient` 只读 GET，严格校验 Envelope、Trace、
`no-store`、项目归属、最小字段、来源状态、页长和 cursor；错误区分会话、
License、权限、归档、失效 cursor 与不可用。新增 `SurveyVersionCreateClient`
和私有 Session POST 桥，支持冻结四类来源形状、完整问题/目标部门快照、强
`If-Match`、CSRF、原 `Idempotency-Key` 和201/Location/ETag/指纹核验。
若网络或回执不明，不自动重发或生成新操作号。辅助函数分别创建精确
`HANDOVER_ITEM` 来源和注明访谈笔记的 `MANUAL` 来源；服务端最终资格不变。

定向含 Session 合同178项先通过；增加两个新客户端测试后定向9项、全量
前端2030项、TypeScript检查及 Vite build 均退出0。随后细化 GET 的 License/
失效 cursor 错误映射，最终定向9项、前端全量2031项、TypeScript与 Vite
build 再退出0。无新后端数据库或真实浏览器/HTTP/PG版本写证据。

下一项 `SUR-07-A07`：把受权页面来源选择、目标部门与人工问题卡片接入，
明确面对面访谈优先；A08 才从干净提交重建非发行包验证真实 Edge/HTTPS/PG。
真人确认、正式信任/安装、Gate/Pilot/Release 仍未通过。
