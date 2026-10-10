# AI-01-A05-P03-A02：Provider Test 内部受权原子提交

日期：2026-10-02；状态：Windows 11 / 隔离 PostgreSQL 18.6 合成验证 PASS；整体 AI-01-A05、Gate 3 未通过。

## 基线与边界

- Phase 2；前置 P01 离线固定探针、P02 不可变结果表 0055、P03-A01 原子 Job/Outbox 队列均完成。依据冻结 API-03 的 `202 JobRef`、CR-AI-002 和 DEC-20261002-642。
- 本项只建立内部 `AIProviderTestSubmitService`，不开放 HTTP、不启动 Worker、不读取 Key 明文、不调用厂商。正式端点策略供给、网络目标防护及对外授权留 P04/P05。
- Session/CSRF 管理员与 License 先验证，写事务内再次验证；Idempotency-Key 以管理员/部署操作作用域和原始 ProviderId/If-Match 指纹锁定。首次请求在行锁下取得当前配置、受控策略及 ACTIVE SecretVersion，写入引用化 Job/Outbox、Audit 和 202 收据后一次提交。重放验证历史成对 Job/Outbox 并返回原 JobRef，不重新检查漂移后的配置/Secret，也不产生新 Audit。

## 验收证据

- 单元：新增 5 项，覆盖首次版本/Secret/策略摘要绑定、原结果重放、版本/状态/Secret 拒绝、权限/审计失败不提交、请求形状/孤立收据失败关闭。旧队列 3 项仍通过。
- 隔离 PG：`validation/ai-01-a05-p03-a02-provider-test-submit/verify.py` 使用临时数据库完整迁移到 head，真实管理员/普通用户 Session、真实 Provider/Secret、两个并发相同 Key 提交，验证一对 Job/Outbox、一份收据和 Audit；原配置版本变化后原 JobRef 重放、同 Key 异命令冲突、Audit 故障原子回滚、payload 仅引用。执行 PASS，临时数据库已删除，PG 服务已停止。
- 后端全量：1946 运行、3 跳过、0 失败；开发 wheel `plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` SHA-256 `78aa45d5d01d9397189c7982ece8914c9ea5229bcf8c389f9cc473e8b5f0d559`，本地构建，不作为可用发行包。

## 遗留与下一项

无新 Migration、公开 API 或依赖；仍需 P03-A03 可选 202 HTTP、P04 Worker/Adapter/外发安全与真实连通、P05 受权结果和激活组合。正式信任源、Server 2025/Debian、质量 Gate/UAT/发行未验。
