# AUD-01-A03 审计只读查询与项目隔离验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结提交 `64cdf09` 的 API-01/02、SC-03、DM-02，及 `DEC-20260924-074`。
- 实现：内部 AuditQueryService + 必需权限 Port、固定 PROJECT/DEPLOYMENT Scope、受限筛选/时间窗、稳定 keyset、脱敏投影。没有公开路由或数据库变更。
- 验收：Windows 11/Python 3.13 后端 99/99；PostgreSQL 18.6 独立库多页查询、跨项目详情不可见、部署管理员不混入项目事件、普通成员不可读部署事件、无权访问拒绝及摘要字段不出投影 PASS。验证入口：`validation/aud-01-a03-audit-read/verify.py`。
- Migration/API：无新增；沿用 `20260924_0005`。无升级步骤，安装更新 wheel 即可。Windows Server 2025/Debian 13 本任务未验证。
- 遗留：权限 Port 未接真实 Session/License/Project 授权；内部 keyset position 不得直接作为外部游标。公开 API 须实现签名、Scope/查询指纹绑定、统一错误与查询权限；导出/Retention 未实施。下一项为 `AUT-01-A01 User/Credential ORM/Migration`，Gate 3/UAT 未通过。
