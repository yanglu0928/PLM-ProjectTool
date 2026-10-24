# SOL-01-A04-P08-P06-P05-P03-P01：多来源 GLOBAL Reference 创建入口

日期：2026-10-09。结果：`MULTI_SOURCE_CREATE_UI_PASS`，限前端合同；单来源与真实 Edge/PG 创建尚未验。

编码前检查：P05-P01/P02 设计与客户端已同步；现有多来源候选页保留逐项原文检查、显式人工确认和撤回。仅改该页面及定向测试，无后端/API/Schema/依赖变化，不让 AI 或脚本代替真实用户确认。

实现：确认成功后只显示“本会话历史确认”，要求管理员填写参考方案名称；点击创建时重取所选每条 GLOBAL Evidence 的受权 Viewer 和当前 Eligibility，重新 Preview 并核对有序 DocumentVersion/Evidence、根文档身份和来源指纹与本会话确认一致。仅提交名称和原五个固定来源字段；服务端仍写时重验最新确认/文件/License/权限。结果是 `REFERENCE_ONLY/DRAFT`，不称正式方案。网络/响应不确定时，先前已保存当前管理员、原 Key 和请求正文，禁止新 Key 再提交；因现无 Create 回查 API，仅提示人工核对服务端审计。确定的失权/来源失效拒绝清空本次准入。合成 UI 点击不是实际业务确认。

验证：新增成功重验和不确定锁定 2 项，前端全量 107 文件/1638 项、typecheck/build通过；既有主包超过 500 kB 提示。真实 Edge、完整单/多来源、正式账户/License、Server 2025、20 并发、Gate 3/UAT/发行仍未验；Debian 13 依用户指令跳过。

兼容/升级/回滚：无数据升级，旧确认/撤回流程保持；可隐藏新增创建区，已生成的确认/Reference/Audit/幂等历史保留。TraceLink：冻结 API-04 → CR-SOL-006/007/009/010 → P06-P02～P04 → P05-P01/P02 → 本 P05-P03-P01 → P05-P03-P02/P04。
