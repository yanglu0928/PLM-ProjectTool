# SOL-01-A04-P08-P06-P05-P04：GLOBAL Reference Create Edge/隔离PG

日期：2026-10-09。结果：`GLOBAL_REFERENCE_EDGE_PG_PASS`，限定 Windows 11、一次性 PG18.6/pgvector、合成私有文件与 Edge 自动化，不是实际真人脱敏确认或发行验收。

编码前检查：依据 P06-P02～P04 服务端合同/Windows组合/隔离PG、P05-P01～P03 前端。复用现有单/多来源 Browser 夹具，仅在显式 `create` 模式挂 GLOBAL Create；旧脚本默认不变。无生产代码、Schema、依赖或冻结 API 变化；测试身份/文件/Edge profile/PG 实例均一次性创建并清理，不读取客户方案库。

多来源：两个不同 GLOBAL 文档版本与 Evidence 按 UI 选择顺序保留；脚本逐项打开固定原文并勾选，Confirm 201 后填写合成名称。Edge 抓取 Create 原 Key 与严格六字段、有序 2 DocumentVersion/2 Evidence，收到 201；隔离 PG 核对 GLOBAL/无项目、`REFERENCE_ONLY/DRAFT`、确认 ID 绑定、2/2 声明计数和单次 `SOL_REFERENCE_CREATED` Audit；继续撤回、确认原 Key 回查及来源回归。

单来源：独立随机隔离 PG/Edge 轮次，1 DocumentVersion/1 Evidence 的 Viewer/原文/确认→Create 201，PG 同样核对版本确认绑定、1/1来源和单次 Audit；撤回/回查及来源回归通过。两轮退出码均 0。Windows 组合此前 P06-P04 已验；本项不把脚本勾选宣称人工事实。

兼容/升级/回滚：仅验证脚本和追溯，无数据升级。可停用测试 `create` 模式，旧人工确认脚本不变；实际 Reference/确认/Audit/收据历史不得删除。正式 License/服务账户、公钥/信任、Server 2025、真实资料人工核查、20 并发、Gate 3/UAT/发行仍未完成；Debian 13 按用户指令跳过。GLOBAL Create 无原 Key 查询，前端结果不确定时仍锁定人工审计核查，后续便捷恢复须独立 Change Request。

TraceLink：冻结 API-04 → CR-SOL-006/007/009/010 → P06-P01～P04 → P05-P01～P03 → 本 P05-P04 → 后续 Reference GET/List/Eligibility 与正式发行证据。
