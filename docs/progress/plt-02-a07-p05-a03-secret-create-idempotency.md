# PLT-02-A07-P05-A03：Secret 创建持久幂等

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A03。输入：冻结 API-01 幂等合同、通用收据 Migration `20260925_0015`、PLT-02-A05 创建/审计事务。前置满足本项；公开写 HTTP 与正式信任源仍未完成。
- Changed：`CreateSecret` 要求合法 Idempotency-Key；在现行管理员/License 复核后，事务内按 actor/部署全局/操作/Key 摘要预约收据。请求指纹只包含 purpose、consumer 和值的 SHA-256 摘要；同请求重放返回原 SecretRef 而不重复加密或审计，异请求返回 `CONFLICT_IDEMPOTENCY`。密文、Audit 与完成收据同事务提交，明文在所有返回路径清零。
- Files：Secret 写 Application/收据 Port、单元与 PostgreSQL 临时库验证、决策/版本/状态记录。
- Migration/API：无新 Migration，复用 `0015`；无公开 API 变更，创建写路由仍关闭。内部 CreateSecret 调用已补齐 Key。
- Tests：Windows 11/Python 3.13 后端 365/365 PASS；PostgreSQL 18 临时库同 Key 顺序/并发重放仅一条 Secret/一次创建 Audit、不同值冲突、审计失败后收据回滚并可用原 Key 成功重试；旧轮换/停用回归 PASS；开发 wheel PASS。临时库已删除且 PostgreSQL 服务停止。
- Result：内部创建持久幂等 PASS；轮换/停用幂等及完整写 HTTP、正式生产信任源未完成，A07 整体未 PASS。
- Known Issues：Receipt 只存摘要/结果引用，不存 Secret，但目标环境正式数据库升级、Server 2025/Debian 13 和用户实际部署未验收；客户密钥不得用于合成测试。
- Next：PLT-02-A07-P05-A04 轮换/停用命令同事务持久幂等，再完成 Secret write-only HTTP 与生产装配。
