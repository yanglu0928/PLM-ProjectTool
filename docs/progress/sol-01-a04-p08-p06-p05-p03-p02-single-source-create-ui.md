# SOL-01-A04-P08-P06-P05-P03-P02：单来源 GLOBAL Reference 创建入口

日期：2026-10-09。结果：`SINGLE_SOURCE_CREATE_UI_PASS`，限前端合同；真实 Edge/PG/真人确认待验。

编码前检查：P05-P01/P02/P03-P01 已记录并验证；此项只补单来源人工核查页的创建入口、当前资格客户端和测试，复用同一冻结六字段及 GLOBAL Create 客户端，不改后端/API/Schema/依赖。当前人工确认只在本会话展示为历史事实，不推断当前有效。

实现：管理员在逐项原文核查并主动提交确认后填写名称；创建前重新获取固定 Evidence Viewer、Eligibility 和 Preview，核对 Document/Evidence 身份、内容链接与历史确认来源指纹；服务端写时仍重验最新确认与物理来源。Session 私有 CSRF，先保存当前管理员/原 Key/请求正文，再提交；结果不确定保留跨刷新锁，不自动重试/换号。确定的失权/来源失效拒绝清空本次准入；成功仅显示 `REFERENCE_ONLY/DRAFT`，不称正式方案。

验证：新增单来源不确定锁定测试，前端全量 107 文件/1639 项、typecheck/build通过；原有单来源确认/撤回测试仍通过。主包超过 500 kB 的既有提示仍在。实际 Edge、正式 License/账户、真人脱敏核查、Server 2025、20 并发、Gate 3/UAT/发行未验；Debian 13 依用户指令跳过。

兼容/升级/回滚：纯前端增量，无数据升级；隐藏创建区可回滚入口，服务端确认/Reference/Audit/收据历史保留。TraceLink：冻结 API-04 → CR-SOL-006/007/009/010 → P06-P02～P04 → P05-P01/P02/P03-P01 → 本 P03-P02 → P05-P04。
