# HND-01-A05-A02：Handover Analysis/Version/Item 读取 Owner

日期：2026-10-05。结论：`HND_01_A05_A02_ANALYSIS_READ_OWNER_PASS`。下一项：`HND-01-A05-A03` Analysis metadata PATCH/ARCHIVE Owner。

## 完成范围

- 新增内部 `HandoverAnalysisReadService` 与 Handover-owned SQLAlchemy 只读仓储，覆盖 Analysis LIST/GET、Version LIST/GET、Item LIST 五个冻结 Operation。
- 五类读取每次重验 License、当前 Session 和 Project 当前成员事实；四类项目角色可读，跨项目、已撤权或失效 License 统一失败关闭，归档项目保留历史读取。
- Analysis 采用 `updated_at DESC, handover_analysis_id DESC` 完整 keyset；Version 采用唯一 `version_no DESC`；Item 采用唯一 `ordinal ASC`。页大小统一限制为 1～200，并以额外一行探测后页。
- Analysis/Version 只投影身份、状态、固定来源和 ETag/指纹；Version 详情只返回 DocumentVersion/AI Task 标识，Item 只返回问题短文本、输入规格、Evidence/Capability 标识和选项，不解析文档路径、Evidence 正文/定位或 AI 输入输出。
- 新增五项四角色只读授权策略，并锁定当前 Project/Member/Department 事实；读取不写 Audit、幂等收据或 Handover 业务表。

## 偏差、兼容与回滚

本项没有 Schema、冻结 API、依赖、配置、Secret、网络或外发变化。A01 表格曾把“签名 cursor”误写入 A02，已按同文 A06 的既定分工更正：A02 只实现内部完整位置，签名 cursor 与 HTTP 留在 A06，不构成基线变更。

回滚可移除读取 Service/Repository 与五项只读策略；不删除或改写任何 Handover 历史。当前尚未挂载 HTTP Router，因此默认应用与 Windows 生产组合的公开行为保持不变。

## 客观验证

- 定向单元：14 项通过（含授权矩阵、输入/位置防御、探测行裁剪及异常仓储失败关闭）。
- Windows 11 / PostgreSQL 18.6：四角色、同时间戳 Analysis 双页、Version/Item 双页、安全引用投影、跨项目/撤权/License 拒绝、归档读取与零业务写入通过；Alembic `head`/`check` 无新增漂移。
- 后端全量：2681 项通过，3 项跳过。
- wheel 解包导入：`HND_01_A05_A02_WHEEL_IMPORT_PASS`；SHA-256 `5e3865d23c5436e5168f4b61504a4166efbba33edf75bd92801724dcb33b16ae`。

已知未完成：A03 metadata PATCH/ARCHIVE Owner；A04 写 HTTP；A05 原子业务送审；A06 五读 HTTP/cursor；A07 Windows 组合与真实 HTTP/PG；Server 2025、Debian 13、Gate 3 和发行验收仍按总状态跟踪。
