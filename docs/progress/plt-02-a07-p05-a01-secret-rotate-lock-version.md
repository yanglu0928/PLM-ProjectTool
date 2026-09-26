# PLT-02-A07-P05-A01：Secret 轮换锁版本对齐

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A01。输入：Gate 2 冻结 API-01 强 ETag/If-Match、PLT-02-A05 内部写服务与 Secret Schema。前置满足；正式写 HTTP 的幂等与生产密钥仍未完成。
- Changed：轮换命令将期望并发条件明确为 `SecretRecord.lock_version`；持久层锁定活动记录时检查该版本，读取当前真实密文版本号，服务据此生成下一密文版本，实际写入再次检查记录锁版本和旧密文版本。陈旧锁版本在加密前拒绝。
- Files：Secret 写 Application/Repository、单元测试、PostgreSQL 临时库脚本、决策/版本/状态记录。
- Migration/API：无数据库变更、无公开 API 变更；写路由仍未挂载。旧内部调用字段名已更新，位置参数只在原验证脚本使用。
- Tests：Windows 11/Python 3.13 后端 361/361 PASS；单元测试覆盖锁版本与密文版本不同、陈旧版本拒绝且未加密；PostgreSQL 18 临时库特意合法增加记录锁版本但不增加密文版本，旧条件拒绝、正确条件轮换、并发仅一成功、密文历史和审计回滚 PASS；开发 wheel PASS。临时库已删除且数据库服务停止。
- Result：内部轮换 If-Match 语义前置 PASS；不代表完整 Secret 写 API 或 PLT-02-A07 PASS。
- Known Issues：创建/轮换/停用公开 HTTP 的 CSRF、Idempotency-Key、If-Match 解析和同事务收据仍未接线；正式 Secret 主密钥/License 信任源、Server 2025 与 Debian 13 未验收。
- Next：PLT-02-A07-P05-A02 强 If-Match 请求边界，随后按写命令分别接持久幂等收据与安全 HTTP。
