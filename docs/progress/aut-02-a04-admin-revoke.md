# AUT-02-A04 管理员批量撤销验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结 API-02/DM-02、`DEC-20260924-081`。
- 实现：仅 Auth 内部按用户批量撤销；必须有管理员权限 Port，默认无适配器时拒绝。目标 User 行锁与 Session 签发序列化；撤销记录和 Audit 同事务，重复执行返回 0。
- 验收：Windows 11/Python 3.13 后端 121/121、wheel 构建 PASS；PostgreSQL 18.6 临时独立库拒权无写入、Audit 失败回滚、两条 Session 批量撤销/旧 Token 失效、重复调用 0 PASS。验证脚本：`validation/aut-02-a04-admin-revoke/verify.py`。
- Migration：无；沿用 `20260924_0007`。API：无新增公开路由；测试权限适配器不是生产授权。Windows Server 2025/Debian 13 本任务未验证。
- 遗留：真实管理员 Session/License/权限适配、Cookie/CSRF/Origin/Host/限流、User 停用和换密命令的同事务接线尚未完成；Gate 3/UAT 未通过。
