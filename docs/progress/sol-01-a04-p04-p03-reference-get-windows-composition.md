# SOL-01-A04-P04-P03：Windows 显式模式 PROJECT Reference GET 组合

日期：2026-10-09；结果：`REFERENCE_GET_WINDOWS_PG_PASS`。此为 Windows 11 隔离 PG/合成信任源验证，非正式发行信任源 PASS。

```text
当前 Phase：Phase 2 Platform Core
输入基线：Gate 2 API-04、DEC-20261009-1114、P04-P01/P02
前置：内部读取 Owner、GET HTTP 合同及隔离 ASGI/PG 已通过
涉及模块/实体：Windows Solution 组合根、production_login 路由装配；无 Schema
涉及 API：显式 --platform 与 --platform-write 的 PROJECT GET；默认/GLOBAL 关闭
权限：真实 Session、当前项目有效成员、有效 License；缺依赖拒启动
验收：模式隔离、真实 ASGI/PG、跨项目/License 负例、后端回归
风险：正式公钥/目标账户 Vault/ACL/HTTPS、List/UI、性能和 Gate 3 待
```

Windows Solution 新增独立只读组合，使用现有 Session、License Guard、项目授权仓储和 Reference 当前版本仓储。`production_login` 仅在 `include_secret_read` 显式模式接入 PROJECT GET；普通登录模式不挂载，GLOBAL 路径仍关闭；写模式复用同一只读组合，不扩大 POST 权限。无 Schema、冻结 API 或依赖变化，可通过移除显式组合回滚，历史数据不变。

Windows 11 一次性隔离 PostgreSQL 18.6/私有来源文件、真实 SessionService/ASGI 验证固定 DocumentVersion/Evidence GET、默认路由 404、跨项目 404、License 拒绝 403；来源/PROJECT 创建和 Alembic drift 回归通过。生产模式合同检查默认、只读、写三种路由边界；单元检查必需依赖缺失即拒启动。后端全量 `3313 passed, 3 skipped, 4871 subtests passed`。正式 License、目标服务账户、Server 2025、Debian 13、20 并发、List/UI 与 Gate 3 仍未通过。TraceLink：API-04/DEC-1114 → P02 GET 合同 → Windows 组合 → 模式合同/隔离 PG 验证。
