# SOL-01-A04-P09-P02：GLOBAL Reference 只读 Owner/仓储

日期：2026-10-09。结果：`GLOBAL_REFERENCE_READ_OWNER_PASS`，仅内部只读 Owner/隔离 PG；公开 GET/List、Windows 装配、前端导航和正式业务资料未验。

编码前检查：Phase 2；冻结 API-04 `SOL_REFERENCE_GET/LIST`、P09-P01 与 DEC-1120 为输入。P06-P05-P04 已有可持久 GLOBAL Reference Create；现有 PROJECT Read/Repository 严格依赖 ProjectId，不能放宽复用。此次只新增 Solution 内部 GLOBAL Query/DTO/Service/Repository、单元与隔离 PG 验证；无 Migration、公开 API、权限扩大、新依赖或跨模块写入。

实现：Service 对每次读取要求当前有效 DeploymentAdmin Session 与 License，Query 不接受客户端 ProjectId；仓储只读取 `scope=GLOBAL/project_id=NULL` 的当前 Root/Version，有序 DocumentVersion 根身份与 Evidence ID，并校验声明计数、连续序号和 GLOBAL 来源身份。List 用 Reference UUID keyset、有界 1～100、固定安全摘要；不复用 PROJECT 游标。内部 GET 保留 ConfirmationId 供一致性证明，但后续 HTTP 不能把它输出为“当前已确认”；撤回后历史 Reference 仍可读，物理来源须通过各自受权端点另查。

验证：单元 5 项/15 子例；Windows 11 一次性 PG18.6 两库：GLOBAL Create→真实管理员 Session GET/List、固定来源顺序、确认撤回后历史读取、无 Session/License 拒绝；独立 PROJECT Create 库证明 GLOBAL 仓储不返回 PROJECT Root，两个脚本回归均退出 0。后端全量结果见 STATUS。无 20 并发/Server 2025/正式 License/账户/真人资料确认/Gate 3/UAT/发行结论；Debian 13 依指令跳过。

兼容/升级/回滚：无数据库/API 变化或数据升级；可停止接线此内部 Owner，已有 GLOBAL Reference、确认/Audit/收据与 PROJECT Read 保留。风险在后续 HTTP 误将内部确认 ID 或历史指纹说成现时资格；P09-P03/P04 应只投影固定身份与安全摘要，并分别执行 Session/License/Scope 验收。

TraceLink：冻结 API-04 → DEC-1120/P09-P01 → P06 GLOBAL Create → 本 P09-P02 → P09-P03 GET / P09-P04 List。
