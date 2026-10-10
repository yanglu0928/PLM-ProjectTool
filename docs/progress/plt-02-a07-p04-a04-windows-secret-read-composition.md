# PLT-02-A07-P04-A04：Windows Secret 只读生产组合根

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P04-A04。输入：Windows 登录组合根、License 真实信任链组合、P04-A01/A02 只读 API、P04-A03 独立游标密钥。代码前置满足；真实发行信任锚/目标账户供给未完成。
- Changed：新增显式 `--platform` 模式，只有 PostgreSQL 就绪且 Schema 当前、License 包内正式公钥/本机 MAC/可信时间密钥可装配、独立游标签名 Vault 密钥可解析时，才在同一应用挂载登录和 Secret 详情/列表。任一项失败整个平台模式拒绝启动并释放数据库；不回退合成 Guard 或登录模式。原默认启动仍仅登录/恢复面。
- Files：Windows 生产入口与启动器、组合契约测试、决策/状态/版本记录。
- Migration：无。API：仅挂载已冻结的两个 GET；Secret 创建/轮换/停用仍关闭。
- Tests：Windows 11/Python 3.13 后端 360/360 PASS；合成组合下可见只读路由、写路由未开放、缺游标密钥失败且释放资源、原登录模式保持；开发 wheel PASS。
- Result：组合代码及合成失败关闭验证 PASS；当前包缺正式签发公钥和目标账户真实 Vault 密钥，`--platform` 不能作为可用生产模式验收，A07 整体未 PASS。
- Known Issues：尚未在真实 PostgreSQL＋正式 License 安装＋目标账户下执行只读端到端；Server 2025/异账户、Debian 13 和 HTTPS 服务部署未验证。P03-A03 真实签发/备份仪式仍待执行。
- Next：推进 PLT-02-A07-P05 Secret 写 API 的 If-Match/幂等/审计前置，或先完成可独立验证的生产密钥/发行准备；不得把合成组合测试当正式交付。
