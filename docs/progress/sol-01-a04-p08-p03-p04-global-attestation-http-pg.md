# SOL-01-A04-P08-P03-P04：GLOBAL 人工脱敏确认 HTTP/PG 隔离验证

日期：2026-10-09；结果：`GLOBAL_ATTESTATION_HTTP_PG_PASS`，仅 Windows 11 隔离 PG18.6、合成管理员 Session、合成来源。未启用 Windows 生产组合，不等于真实管理员已确认任何客户资料。

编码前检查：Phase 2；WBS P08-P03-P04；输入 CR-SOL-009、P08-P02 增量 API 合同和 P03-P03 可注入 Router；前置内部来源 Preview/Confirm/Revoke、当前管理员 Session/PG 夹具与 HTTP 合同均通过。本项仅修改隔离验证夹具，涉及 Solution 确认记录/Audit/幂等收据和 Document/Evidence 来源，三项 API、管理员/License/CSRF 权限；无生产 Schema、API、依赖变更。验收为真实 PG 固定来源、Preview 无写入、错误指纹拒绝、Confirm/Revoke 重放单次效果、请求安全失败关闭。风险为合成 Session/点击不构成业务人工核查。

以原有私有文件、Document/Evidence、Auth 与确认/撤回真实 PG 夹具为基础，插入可注入 ASGI Router 回调；确认 Preview 投影包含正确 Document 根/版本和 Evidence 身份、不包含文件名，确认表无写入。错误指纹 `SOURCE_SNAPSHOT_CHANGED` 409，错误 CSRF/Origin 403。正确指纹 Confirm 201，同 Key 再请求 201 且确认行和确认 Audit 各一；同 Key 异载荷 409。Revoke 200、同 Key 重放 200、新 Key 对既已撤回项 409，撤回 Audit 一条。随后原夹具继续验证真实来源文件和解析节点篡改、Evidence 撤回及确认 Proof 失效。

首次运行到 Audit 数量检查时，验证脚本误写不存在的 `plm.audit_events` 表；改为实际 `plm.aud_events` 后完整复验退出码 0，隔离 PG 停止并移除临时目录。未更改生产行为。全量后端测试沿用前项 `3330 passed, 3 skipped, 4919 subtests passed`；本项新增隔离脚本通过。兼容/回滚：仅验证脚本及原夹具可选回调，无迁移或部署动作；移除回调可恢复原夹具行为。

未验：Windows 生产组合、前端逐项文档查看与明确勾选、真实人工业务确认、正式 License/目标服务账户、Server 2025、20 并发/Gate 3/发行；Debian 13 依用户指令跳过。TraceLink：CR-SOL-009 → P08-P02 合同 → P03-P03 HTTP → P03-P04 真实 PG/ASGI → 后续 Windows/UI。
