# PRJ-04-A11-P01：成员角色/部门更新可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A11-P01。输入：冻结 API-01/02、PRJ-02-A03 内部版本化更新服务、现行 Session/CSRF/License 安全边界；决策 DEC-20260925-070。
- Changed：新增仅显式注入的 `PATCH /api/v1/projects/{project_id}/members/{project_member_id}`。可信 Origin、Session/CSRF、严格强 If-Match、有界 JSON；只接受非空 role/department_id 子集。调用内部 ProjectManager 授权、跨项目归属、有效部门及最后负责人保护；200 返回安全 MemberView 与强 ETag。默认/当前 Windows 平台组合不挂载，仍 404。
- Files：Project 成员 PATCH Router、应用工厂注入点、契约与临时 PostgreSQL HTTP 验证、决策/状态/版本记录。
- Migration：无新增；目标库需已有成员历史 `0014`。API：冻结路径的可选实现，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 416/416 PASS；PostgreSQL 18 临时库 HTTP 200/ETag、旧版本 409、跨项目/CustomerManager 404、最后负责人保护 422、合成 License 403、仅一次历史/Audit 与既有回滚/归档/迁移验证 PASS；开发 wheel PASS。临时库已删除，服务停止。
- Result：可选 HTTP 与隔离合成端到端 PASS；Windows 显式平台组合、正式信任源、PRJ-04 整体、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；正式发行信任源待供给。
- Next：PRJ-04-A11-P02 接入 Windows 显式平台组合并复验门禁与真实 Session。
