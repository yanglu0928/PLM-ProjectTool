# TRC-01-A02：TraceLink 受保护持久结构

- Changed：新增 `plm.trc_links` 双端固定 Object/Version 多态引用、Scope/Project 授权快照、受控关系、创建 Actor/Trace 与状态/替代引用。数据库校验类型白名单、方向、自环、活动边唯一；触发器只允许 ACTIVE→SUPERSEDED/REVOKED，禁止静默改写与删除。无全局 Object Registry；多态目标存在/正式性、权限、无环和 Audit 必须由后续 Owner Port/TraceService 验证。
- Files：Trace ORM、Migration `20260926_0029`、ORM/迁移合同测试、`validation/trc-01-a02-trace-schema/verify.py`；公开 API/新依赖：无；版本 `0.1.0.dev0`。升级前备份；有任何 Trace 历史时降级拒绝。
- Tests：Windows 11/Python 3.13 后端 587 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 旧数据升级、空表降级再升级、ORM parity、双 Scope/跨项目/未知类型/自环/活动重复/终态/保留约束 PASS；开发 wheel PASS，SHA-256 `dba5869382391d26705cd95bf157824e4be9c39ddd77242dbf848aef7bcd3bc0`。
- Result：Schema 和数据库历史边界 PASS。测试边仅用合成目标 ID，不证明目标对象存在、已确认、授权或无环；没有正式 Trace 写路由，TRC-01 整体、Gate 3 与可用程序包未通过。
- Next：TRC-01-A03 目标 Owner Port 与固定版本来源证明；Windows Server 2025 本项未运行，Debian 13 按用户指令暂不验证。
