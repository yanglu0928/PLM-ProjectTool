# AI-01-A05-P04-A03-P01：SecretResolver 精确版本绑定

日期：2026-10-02；状态：Windows 11 / 隔离 PostgreSQL 18.6 合成验证 PASS；未开放 AI 传输或 Worker 循环。

## 基线与任务边界

- Phase 2；输入 P03 首次 Job 快照含 SecretVersionId、P04-A02 预检及 CR-AI-002/DEC-20261002-646。现有 SecretResolver 信封仅含 version_no，不能精确匹配 Job 的版本 UUID；前置已满足。
- 本项仅在 Platform 内部信封添加不进入 repr 的 SecretVersionId，PostgreSQL Store 从当前 ACTIVE 版本填充，Resolver 增加可选 `expected_version_id`。传入时必须在解密前精确相等，否则安全拒绝并审计 DENIED；未传参数的既有消费者行为保持。无 Schema、公开 API、依赖或网络调用。
- 验收：正确版本一次性读取且缓冲清零；轮换后旧 Job 版本在解密前拒绝；缺少/畸形版本拒绝；全量既有调用回归。风险：读取后的版本可能再次轮换，本项不授予发送许可；后续 A03-P02 必须发送前再核查。

## 证据与后续

- 单元新增 2 项：匹配、错配、缺版本及畸形版本在解密前失败关闭；原 Secret 单元继续通过。隔离 PG 脚本 `validation/ai-01-a05-p04-a03-p01-secret-version/verify.py` 执行真实 SecretVersion 轮换，证实旧版本拒绝、版本匹配可取、明文缓冲退出清零；不使用真实 Key 或网络。临时库已删除、PG 服务停止。
- 后端全量 1957 项运行、3 项跳过、0 失败；开发 wheel `plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` SHA-256 `929de2d77529833b0607566652e7110e9a333d7d689b50a6a5dc5fd65effa210`，不是可用发行包。
- 下一项 P04-A03-P02 受限传输、本机合成端点、DNS/IP/重定向/TLS/超时/响应上限及发送前重新核验；随后 P04-A04 结果/终态。真实厂商外发、正式信任源、质量/三平台/Gate/UAT/发行未验。
