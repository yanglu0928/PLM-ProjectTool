# PRJ-04-A16：Department 停用前置核查

- 当前 Phase：Phase 2 Platform Core；当前 WBS：PRJ-04-A16 前置核查。
- 输入基线：Gate 2 冻结 API-01/02、PRJ-03-A04 内部停用、PRJ-04-A14/P01～P03 与 A15/P01～P02。
- 前置任务：已满足；内部停用和权限/成员在用检查已验证，公开路由尚未实现。
- 涉及模块/实体：Project、Platform 通用收据；Department、Audit、首次结果快照。
- 涉及 API/权限：`POST /api/v1/projects/{project_id}/departments/{department_id}:deactivate`；ProjectManager、当前 Session/CSRF、License、Idempotency-Key、强 If-Match、跨项目 404。
- 验收标准：同 Key 首次结果重放、不重复停用/Audit；异载荷冲突；仍有 ACTIVE/SUSPENDED Member 时 409 `PROJECT_DEPARTMENT_IN_USE`；默认应用关闭，平台门禁关闭失败。
- 风险：当前内部服务无持久幂等/快照，且通用错误码未登记；直接公开会违反冻结契约。见 CR-PRJ-005。
- 结论：前置核查 PASS，但公开接线 BLOCKED，先执行 PRJ-04-A16-P01 数据/内部服务增量，再 P02 可选 HTTP、P03 Windows 平台组合；不把 A16 整体标为 PASS。
