# EVD-01-A04-P03-A08-P17：GLOBAL 人工资格命令客户端

日期：2026-10-01；Phase 2 Platform Core；结果：`FRONTEND_GLOBAL_COMMAND_PASS / UI_WRITE_CLOSED`。

编码前检查：输入冻结 `EVIDENCE_SET_ELIGIBILITY` GLOBAL 合同、Windows 显式写组合、P16 GLOBAL 受权只读页与 P15 当前状态。仅扩 Session/Evidence 前端客户端和测试；无后端、Schema、角色、冻结 API 或依赖变化。管理员当前会话、未强制改密、固定 GLOBAL Viewer、当前 CANDIDATE 强 ETag、人工结论/理由及 16～128 字符原 Key 必备。响应仍是首次回执，不作当前状态证明；不确定结果不自动重发。

新增 GLOBAL POST `/api/v1/global/evidence/{evidence_id}:set-eligibility` 传输，带同源 Cookie/CSRF、If-Match、Idempotency-Key、JSON Body 和超时互斥。复用严格首次响应校验，补项目与 GLOBAL Viewer 内容路径相符检查；项目身份或项目 Viewer 不得用于 GLOBAL 写。定向 9 项、前端全量 1,060 项、typecheck/build PASS。网络失联仅返回不确定，不重发或更换 Key。

兼容：前端方法增量，项目写入仍通过原路径；无迁移。回滚停用新方法即可，服务端历史保持。GLOBAL 页面尚未接资格表单和请求前操作号持久保存，故写入口继续关闭；真实浏览器、正式信任和 Gate3未验。
