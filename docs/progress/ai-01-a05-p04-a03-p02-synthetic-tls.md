# AI-01-A05-P04-A03-P02 受限探针传输与合成 TLS 验证

- 日期：2026-10-02；版本：`0.1.0.dev0`；依据：CR-AI-002、DEC-20261002-647、P04-A02 当前事实预检、P04-A03-P01 精确 SecretVersionId。
- 产出：内部单次 `ProviderProbeRunner` 与钉住 IP 的 HTTPS 传输；初始/发送前/发送后三次预检，版本精确绑定的 SecretResolver 只在发送期短时使用 Key；仅向受控 FQDN/443 发送固定 `ping` 最小 JSON，不使用系统代理，不跟随重定向，不记录 Key、响应正文或原始异常。
- 安全边界：生产 DNS 全部候选均须为公网 global IP，TLS 仍按原域名以系统 CA 验签；连接/读取超时、请求和响应大小及 JSON 响应形状受限。本机测试子类才可将地址覆盖为 `127.0.0.1` 并信任临时生成 CA。该覆盖不在产品模块或组合中。
- 验证：Windows 11 本机合成 TLS 服务固定 Host/Authorization/Body、临时 CA 信任与系统 CA 不信任、重定向/过大/非法响应/慢响应拒绝、密钥缓冲清零；单元 6 项；后端全量 1963 项运行、3 项跳过，退出码 0；开发 wheel 构建见版本说明。
- 兼容性/升级/回滚：无 Schema、依赖、公开 API 或冻结合同变化，无数据库升级；内部调用未接生产 Worker，撤内部 Runner/Transport 调用可回退，保留既有 Job/Secret/Audit 历史。
- 剩余：预检与实际发送之间仍有微小时序窗口，A04 发布必须再次核查当前 fencing/配置/Secret；Worker 轮询、正式目标网络/信任、真实厂商 Key/外发、质量、Server 2025/Debian、Gate 3/UAT/可用程序包均未验证或开放。本项 PASS 不代表整体 Provider Test 或发行 PASS。
