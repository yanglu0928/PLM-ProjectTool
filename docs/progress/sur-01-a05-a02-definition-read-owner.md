# SUR-01-A05-A02：Survey/Version 读取 Owner

日期：2026-10-06。结论：`SUR_01_A05_A02_DEFINITION_READ_OWNER_PASS`。下一项：`SUR-01-A05-A03` Survey metadata PATCH/ARCHIVE Owner。

## 完成范围

- 新增内部 `SurveyReadService` 与 Survey-owned SQLAlchemy 只读仓储，覆盖 Survey LIST/GET 和 Version LIST/GET 四个冻结 Operation；本项不挂公开 Router。
- 四类当前 Project 成员每次读取均重验 License、Session 与 Project 成员事实；跨项目、撤权或失效 License 失败关闭，归档 Project 保留历史读取。
- Survey 采用 `(updated_at DESC, survey_id DESC)` 完整 keyset，Version 采用唯一 `version_no DESC`；页大小固定 1～200，并以额外一行探测下一页。
- Survey 详情返回强 ETag；Version 详情按固定顺序返回问题、选项、条件、四类来源引用和目标部门。Handover、Capability、Document 只返回类型化固定标识，不跨模块展开正文、文件路径或存储定位；人工来源说明保留在当前 Project 授权边界内。
- 新增四项 `ALL_MEMBERS` 只读授权策略并锁定当前 Project/Member/Department 事实；读取不写 Audit、幂等收据或 Survey 业务表。

## 偏差、兼容与回滚

本项没有 Schema/Migration、冻结 API、依赖、配置、Secret、网络或数据外发变化。A01 对签名游标的要求由 A06 HTTP 层实现；A02 只保留完整内部位置，避免把传输签名逻辑下沉到 Application Owner，不构成基线变更。

回滚可移除读取 Service/Repository 与四项策略；不会删除或改写任何 Survey 历史。公开应用行为保持不变，A06 前仍无 Survey 读取 URL。

## 客观验证

- 定向单元：14 项通过，覆盖授权策略、Session 脱敏、输入/位置防御、探测行裁剪、Version 倒序及仓储异常失败关闭。
- Windows 11 / PostgreSQL 18.6：四角色、同时间戳 Survey 双页、Version 双页、完整问题/选项/条件/四类来源/部门投影、跨项目/撤权/License 拒绝、归档读取、零业务写入及 Alembic `head/check` 通过。
- 后端全量：2823 项通过，3 项跳过。
- wheel 内容：`SUR_01_A05_A02_WHEEL_IMPORT_PASS`，1042 entries；SHA-256 `01594a8a60323989143767bc9a35439ff0e8fd0d9494eb32a9c03b702762b1fb`。

已知未完成：A03 metadata PATCH/ARCHIVE Owner；A04 五个普通写 HTTP；A05 原子业务送审；A06 四读 HTTP/cursor；A07 Windows 组合与真实 HTTP/PG；Survey Round/Response/Conclusion、Server 2025、Debian 13 实机、Gate 3 和发行验收仍按总状态跟踪。
