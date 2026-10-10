# SOL-01-A04-P08-P02：GLOBAL Reference 人工确认增量 API 合同

日期：2026-10-09；结果：`GLOBAL_REFERENCE_CONFIRMATION_CONTRACT_RECORDED`，仅合同/追溯完成，不是路由或人工确认 PASS。

编码前检查：Phase 2 Platform Core；WBS P08-P02；输入冻结 API-01/API-04、CR-SOL-006/007/009；前置 P08-P01 已记录缺口；涉及 Solution 内部确认/撤回、Document/Evidence 受权来源和 Windows/前端后续组合，不变更现有实体/Schema。新增三个 GLOBAL 白名单 Operation 及当前 Session/CSRF/License/管理员约束；验收为精确请求/响应、预览不写、确认写时重验及预览指纹栅栏、撤回保历史、默认关闭。风险为新 API 尚无实现证据，不能自动出具真实人工声明。

合同详见 `docs/api-contract/solution-reference-deidentification-v1-increment.md`：Preview 用 POST 承载有序来源集合但不写；Confirm 必须带回预览的 `expected_source_fingerprint`，服务端从物理来源现时重算并拒绝漂移，实际管理员需主动输入声明；Revoke 使用固定原因码并保留 Audit/幂等历史。成功结果不创建 Reference、不标记 Eligibility。默认路由和 GLOBAL Create 继续关闭。P08-P03 实现前需核对现有内部 Owner 的指纹栅栏与错误映射，P04～P06 逐项验收 Windows/前端/Edge。

本项无程序运行、Schema 迁移或新依赖；验证仅为冻结 API 操作表、内部命令 DTO 与 CR-SOL-009 对账。正式 License/目标账户、实际人工确认、Server 2025、20 并发、Gate 3/发行未验。Debian 13 依用户指令跳过。

TraceLink：冻结 API-04 → CR-SOL-006/007/009 → P08-P01 → P08-P02 增量合同 → P08-P03～P06。
