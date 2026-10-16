# PRJ-05-A08-P04：Windows 11 成员角色/部门 PATCH 浏览器与数据库验证

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机、隔离合成信任源，不是正式发行验收）。输入为 Gate 2 冻结 `PROJECT_MEMBER_PATCH`、P01～P03 和 DEC-20260928-445。
- Changed：扩展自有 `validation/prj-05-a04-browser-project/serve.py` 独立 `--member-patch-api-only`/`--member-patch-browser` 模式，随机 PostgreSQL 库/角色、临时 Vault 测试凭据、合成负责人/目标成员和两个 ACTIVE 部门；只测试本机隔离资源。不改生产程序、API、权限、Schema/Migration 或依赖。
- 验证：真实 HTTP/PG 模式 exit 0：匿名 401、非负责人 404、无 CSRF 403、跨项目 404、目标角色/部门一次 PATCH 200/`"v1"`、旧版本 409、同值操作 200/`"v1"`；SQL 一条成员变更和一条 `PROJECT_MEMBER_PATCHED` 审计，临时库/角色/Vault 清理。真实浏览器模式由合成负责人经登录→项目→成员历史→目标成员选择→角色/ACTIVE 部门→明确确认→提交，显示 `"v1"` 成功回执，重读列表显示目标角色/部门；SQL 版本 1、一条审计，模式 exit 0，临时资源清理 PASS。浏览器提交未使用客户数据或真实发行密钥。
- 修复与中断：首轮浏览器页面操作成功，但 fixture 沿用旧模式“两条 Session”断言而退出 1，未据此标 PASS；修正该模式单 Session 断言。随后会话中断导致一个随机测试库/角色及 Vault 测试凭据残留；确认零活动连接和测试命名后精确清理，未动其他数据。最终重新启动服务和 fixture、完整浏览器/SQL/清理链 exit 0。PoC PostgreSQL 原为停止状态，最终仍为停止。
- 兼容/升级/回滚：兼容 DB head `20260927_0049` 和冻结 `/api/v1`；无程序升级或数据迁移。回滚撤本 fixture 模式即可，P01～P03 及后端保持不变。
- Known Issues/Next：合成 Guard/密钥不代表正式信任锚；未验证 Server 2025/Debian、HTTPS、CR-AUT-008 性能、POC-03 质量、Gate 3/UAT/发行包。下一独立 WBS 先做项目成员状态前端的 Scope/安全前置核查，不把本次 PATCH PASS 外推到状态命令。
