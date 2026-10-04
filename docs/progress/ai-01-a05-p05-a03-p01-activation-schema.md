# AI-01-A05-P05-A03-P01：Provider 激活首次响应快照 Schema

日期/版本：2026-10-02 / `0.1.0.dev0`；依据：冻结 API-03、CR-AI-002、DEC-20261002-653。

编码前检查：Phase 2；P05-A01 历史 Job 读取及 P05-A02 当前证明已验。通用幂等收据只保留结果引用，不能在 Provider 后续暂停后重建原始 200 ACTIVE/ETag，因此先完成 Owner 不可变响应快照，再做激活命令。只涉及 AI Provider ORM/Schema `20261002_0056`、迁移库存测试与验证夹具；不改 API、权限、技术栈或依赖。空库与既有探针数据升级、空表 down、非空拒绝 down、归属/唯一/不可变及 ORM 漂移为验收标准。

实现：`ai_provider_activation_results` 保存 Provider/config/成功探针引用、actor/Audit/trace、前态、固定 ACTIVE、请求锁版本及首次响应锁版本；复合 FK 绑定探针/Provider/config，唯一 `(provider,lock_version)` 与 Audit，约束 `lock_version=expected+1`，触发器禁止 UPDATE/DELETE/TRUNCATE。无 Key、端点或响应正文。通用收据未来通过 `activation_result_id` 引用该行。迁移前备份；空表可回滚至 0055，非空历史禁止物理降级，应用回退只能撤入口并保留历史。

验证：Windows 11 隔离 PostgreSQL 18.6 两库：空库 0055→0056→0055→0056，既有两条探针结果的 0055→0056；`alembic check` ORM 漂移 0；错误 Provider/探针、缺 Audit、锁版本不匹配、状态不符、更新/删除/清空均拒绝；非空 down 拒绝。初次后端回归 2 项失败为测试固定在旧迁移头/旧 ORM 清单，更新断言后定向 7/7、全量 1992 运行/3 跳过。开发 wheel SHA-256 `c0766e1873bcbd62927f85f7f4f32ad5b9e8913827c721f9ffc32b8f4ba945d4`。隔离数据库已删除、临时 PG 服务已停止。

边界：P01 没有激活 Provider；P05-A03-P02 仍需同事务管理员授权、版本/幂等/当前证明、状态写入、Audit、快照和收据。公开 HTTP、Windows 正式组合、生产 Worker/真实外发、Server 2025/Debian、Gate/UAT/可用包均未验证。
