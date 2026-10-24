# AI-01-A05-P05-A01：Provider Test Job 受权安全读取

日期/版本：2026-10-02 / `0.1.0.dev0`；依据：冻结 API-03 JobView、CR-AI-002、DEC-20261002-651。

编码前检查：Phase 2；前置 P03 原子提交、P04 单次 Worker 和不可变结果已验证。仅涉及 AI Owner 证明查询、Jobs 内部结果类型枚举及 Windows 既有 Job 读取组合；不改实体、Schema、公开 API、权限或依赖。验收为当前部署管理员经 License/Session 授权后，同事务核对 Job/Outbox/结果归属，失败关闭且不泄露 Secret/正文。风险是历史成功误作当前配置激活许可；因此只给历史结果引用，激活重验另列 P05-A02。无迁移；回滚撤 Owner 注册并保留历史。

实现：`('ai','AI_PROVIDER_TEST')` 注册至既有 Job Detail/List Owner；严格检查 DEPLOYMENT 原 actor、Job/Outbox 不可变快照、配置版本、SecretRecord/SecretVersion、策略摘要及 Job attempt/fencing。仅 SUCCEEDED 且唯一成功结果返回 `AI_PROVIDER_TEST` `result_ref`；失败、未完成及取消不返回结果内容。新读取不授权结果下载或 Provider 激活。

验证：Win11 隔离 PostgreSQL 18.6 实际 Session/管理员权限、Job/Outbox 错配、缺成功证明、合法成功证明和 License 失效，`validation/ai-01-a05-p05-a01-job-read/verify.py` PASS；定向单测 5/5；后端全量 1987 运行/3 跳过；开发 wheel SHA-256 `0ff067c507c68a6fbacaa787ba668dc88341e0c08395605862d9b56395902fc0`。隔离数据库已删除、临时 PG 服务已停止。

边界：未验证正式 Windows API 进程 HTTP 端到端、当前配置/Secret/策略激活资格、生产 Worker 守护、真实厂商外发、Server 2025/Debian、Gate 3、UAT 或可用程序包。下一 WBS：`AI-01-A05-P05-A02` 当前激活证明重验。
