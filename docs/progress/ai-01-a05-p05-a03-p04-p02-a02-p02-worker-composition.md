# AI-01-A05-P05-A03-P04-P02-A02-P02：Windows 探针 Worker 信任源组合

日期：2026-10-02；状态：限定范围 PASS。依据 CR-AI-002、DEC-20261002-659、A02-P01 审计适配器及单次 Worker。

## 完成范围

- Runner 首次预检后绑定该快照及 trace；审计绑定失败在打开 Transport 前报 `PROBE_SECRET_UNAVAILABLE`。SecretResolver 保持明文交付前持久审计，退出清零。
- Windows 未挂载工厂只接收 BootstrapSettings，从其受控策略来源与当前账户的数据库、License、SYSTEM Actor、Vault `secret-master-v1` 组装 PostgreSQL SecretStore、AES-GCM、专属 Job 组件、持久审计及生产默认的钉 IP HTTPS Transport。缺策略、缺主钥或身份失败时拒绝构建；已创建数据库运行时被释放。
- 不注册服务、不领取 Job、不打开对外连接。A02-P03 才处理维护模式准入、进程生命周期、公开 Test 路由及与 Activate 的同源装配。正式目标账户 Vault/信任、真实外发、Server 2025/Debian、Gate 3/UAT/可用包未验。

## 证据与回滚

- Win11 单元定向 8 项：非 Windows/空策略先于 DB 拒绝、Vault 异常释放、真实组件注入且不运行、审计作用域/trace 清理与绑定故障发送前拒绝。
- `validation/ai-01-a05-p05-a03-p04-p02-a02-p02-worker-composition/verify.py`：一次性隔离 PG18 与本机合成 TLS 的 IDLE、固定 POST 成功、重定向失败；两个 Job 均持久记录 SYSTEM/原 actor/SecretVersion/trace；没有外部 Provider 出站。全量后端 2014 项运行、3 跳过；开发 wheel SHA-256 `1f94193dfee960c7191012ee6c6e08d96e22af16f46ec244c14d2ec23e31678b`。
- 无数据库或公开合同修改。撤未挂载工厂与可选作用域注入即可回退，已提交审计及 Job 历史不删除。
