# PRJ-05-A10-P03：Windows 11 部门历史浏览器与数据库验证

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机隔离合成信任源，非正式发行验收）。输入为 PRJ-05-A10-P01/P02、冻结 Department GET 与 DEC-20260929-452。
- Changed：自有 Project 浏览器 fixture 新增独立 `--department-history-api-only`/`--department-history-browser` 模式，随机 PostgreSQL 库/角色、临时 Vault 凭据、合成负责人及52条部门（末页一条 INACTIVE）。不改生产程序/API/权限/Schema/Migration/依赖。
- 验证：API-only exit0：匿名401、非成员部署管理员404、跨项目404，负责人固定50+2分页、唯一52条含一条停用；SQL 52行/一条停用/无部门写审计，资源清理 PASS。真实浏览器由合成负责人登录→项目详情→部门历史，首屏50条、续页显示末尾两条与“已停用”；fixture exit0，SQL同样52/1/零写，库/角色/Vault/服务清理 PASS。PoC PostgreSQL 恢复原停止状态。
- 修复：首轮 API-only SQL 断言引用不存在的审计列而退出1，修正为部门操作 Audit action 后完整重跑 exit0。首轮浏览器已显示末页，但沿用旧模式两次Session断言退出1；修正为本模式实际一次登录，再完整浏览器/SQL/清理 exit0。失败轮次均不计PASS。
- 兼容/升级/回滚：兼容 DB head `20260927_0049`、冻结 `/api/v1`；无升级步骤。回滚撤独立 fixture 模式，P01/P02和后端保留。
- Known Issues/Next：合成Guard/密钥不代表正式信任锚；Server2025/Debian、HTTPS、CR-AUT-008性能、POC-03质量、Gate3/UAT/可用包仍待。下一 WBS 部门创建前端安全传输前置。
