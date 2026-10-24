# HND-05-A04-P03：交接校验与送审 Windows 11 非发行包验收

日期：2026-10-25；状态：`PRECHECK_COMPLETE / PACKAGED_EDGE_PG_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A04-P03`；只验证已实现的 DRAFT 当前来源校验与客户评审送审，不改变冻结 API/Schema/权限。|
|输入基线|已同步提交 `cd1c51e9`；HND-05-A02-P04 固定非发行候选 SHA `3e84a42c3c22fd5f02ec5a13a35bc86d28394f9d1cf9b846952bdfa8cf2cb209`；A03-P01/P02 与 A04-P01/P02 前端合同测试通过。|
|前置|既有包内合成项目固定文档、交接分析、PROJECT Evidence、当前批准 GLOBAL Capability 与两张 DRAFT 卡片的验收夹具可复用；必须重新打入当前前端，不把旧 ZIP 当成本轮证据。|
|正式约束|送审前 `NEED_CONFIRM` 卡片须有同一 `analysis_item_id` 的非取消 Action；必须通过正式 Handover Action API 创建，不能改库伪造覆盖。客户确认人须为当前项目有效成员，服务端事务复核。|
|验收|清洁解包逐件哈希；Edge/HTTPS/隔离 PG 生成 DRAFT 后打开校验报告，核对真实 Audit/回执及同号重放；先验证缺 Action 时送审拒绝，再建正式 Action 并送审至 IN_REVIEW，核对唯一 Review/Round/Audit/收据、同号重放及匿名/无项目权限/不合格 Reviewer 负例；临时信任与进程清理。|
|风险|仅 Windows 11 合成信任，非真人客户确认、正式公钥/服务账户、离线安装升级、Gate 3～7 或三平台发行；不上传 ZIP/客户数据/秘密。|

前置满足，可开始本 WBS。验收结论仅以固定候选、实际浏览器请求和 PG 事实填写。
