# AI-01-A05-P04-A02：Provider Test 执行前版本与许可预检

日期：2026-10-02；状态：Windows 11 / 隔离 PostgreSQL 18.6 合成验证 PASS；仅内部预检，不是外发许可。P04/A05/Gate 3 仍开放。

## 基线与边界

- Phase 2；P04-A01 领取/fencing、P03 提交、P01 受控策略、P02 结果 Schema 均已验证。输入 CR-AI-002、DEC-20261002-645。
- 模块：AI Application 调用 Jobs 专属当前租约检查、Provider 当前配置行锁、Platform ACTIVE SecretVersion 元数据证明及运行 License Guard；无新 API/Schema/依赖。预检不解密 Secret、不开网络、不写结果或改变 Job 状态，Worker 循环仍关闭。
- 验收：首次 Job 的 Provider/ConfigVersion/SecretVersion/固定策略 SHA-256 与当前事实一致，fencing 和 trace 仍有效；License 前后检查；任何漂移失败关闭，错误只返回安全码。

## 实施与证据

- 提交与预检共用 `probe_policy_sha256` 规范摘要，避免相同策略按两种方式计算。预检短事务内检查 Jobs 当前租约和 Provider/Secret 行锁，返回仅内存的固定探针计划，不保存端点 URL/Key/正文。
- 单元新增 3 项，覆盖匹配、配置/状态/策略/Secret 漂移、旧租约/trace/License 拒绝。`validation/ai-01-a05-p04-a02-preflight/verify.py` 在隔离 PG 真实 Session/Provider/Secret/Job/Lease 上验证正确预检、错误 fencing、License 拒绝、策略端点变化、Secret 停用及实际轮换、配置实际升版；没有结果行或网络动作。临时库已删除，PG 服务已停止。
- 后端全量 1955 项运行、3 项跳过、0 失败。开发 wheel `plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` SHA-256 `225e71f6623c7deecb37b9f55476d5351502f8d16be789dc94f759691539c8bd`，非发行包。

## 遗留与下一项

现有 SecretResolver 信封只有版本号而无 SecretVersionId，预检之后状态也可能变化；因此预检结果不能复用作外发凭证。P04-A03 需要版本绑定的 Secret 使用、发送前重新校验、受限目标/TLS/重定向/超时与本机合成端点验证；P04-A04 需 fencing 下不可变结果/Job 终态。真实厂商外发、正式信任源、质量/三平台/Gate/UAT/可用程序包均待。
