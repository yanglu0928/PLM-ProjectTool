# TRC-01-A07-P01：TraceLink 撤销前置核查

日期：2026-10-02；Phase 2；状态：**PRECONDITION_BLOCKED，转 Schema 前置 P02**。API-02 已冻结撤销路径和 ProjectManager/关系 Owner；当前 PROJECT 创建与持久收据/Audit 组合可复用。Trace 表有合法的 ACTIVE→REVOKED 守卫，但没有 API-01 状态命令要求的 `lock_version`，也没有当前关系 Owner 身份证明。不能以“状态列能更新”视作撤销命令可发布。

依据 `CR-TRC-003` 选择先加数据库拥有的资源版本，再做 PM 内部撤销、公开接口及关系 Owner 证明。普通用户无权、跨项目、终态重放、并发、过期 License、Audit 回滚均须实测。此任务仅静态核查，无代码/API/Schema/数据修改或新业务测试；Gate 3 与发行包仍未通过。
