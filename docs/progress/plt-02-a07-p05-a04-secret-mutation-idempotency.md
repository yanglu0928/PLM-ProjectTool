# PLT-02-A07-P05-A04：Secret 轮换与停用持久幂等

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A04。输入：冻结 API-01 幂等/强版本、通用收据 Migration `20260925_0015`、P05-A01 记录锁版本和内部轮换/停用事务。前置满足内部命令改造；公开写 HTTP/正式密钥仍缺。
- Changed：`RotateSecret`/`DisableSecret` 强制合法 Idempotency-Key；管理员与 License 复核后事务内预约 actor/部署全局/操作/Key 摘要收据。轮换请求指纹仅含 SecretRef、期望锁版本和新值 SHA-256；停用仅含 SecretRef/锁版本。完成收据指向不可变密文版本，重放核对版本归属并返回原结果，不再次加密、变更状态或审计；不同请求冲突。值在所有轮换返回路径清零。
- Files：Secret Application/Repository、单元及 PostgreSQL 临时库验证、决策/版本/状态记录。
- Migration/API：复用 `0015`，无新 Migration 或公开 API 变更，写路由仍关闭。
- Tests：Windows 11/Python 3.13 后端 366/366 PASS；PostgreSQL 18 临时库同 Key 并发轮换/停用仅各一次真实状态与审计变更，陈旧新 Key 拒绝、异请求冲突、密文历史与旧 Audit 回滚回归 PASS；开发 wheel PASS。临时库已删除，数据库服务停止。
- Result：内部轮换/停用同事务幂等 PASS；PLT-02-A07 公开写 API、正式信任源及 Gate 3 未通过。
- Known Issues：写 HTTP 的 JSON 值解析、CSRF/Host/Origin、If-Match/Key 映射、脱敏错误/响应与生产组合仍未完成；Server 2025/异账户和 Debian 13 未验证。
- Next：PLT-02-A07-P05-A05 Secret write-only HTTP 创建接口，再分别接轮换/停用；正式生产主密钥/License 和目标环境发行单列验收。
