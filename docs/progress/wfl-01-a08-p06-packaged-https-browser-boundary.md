# WFL-01-A08-P06：当前候选外部 HTTPS 烟测与浏览器边界

2026-10-02 / Phase 2 / `PARTIAL_PASS_BROWSER_BLOCKED`。输入为 `WFL-01-A08-P05` 固定 Windows 11 非发行 ZIP，SHA-256 `6b0cd4978d5526554443d6ab1b0528ddd4c2feebfa7690c41af627fe55887acb`、本地已逐件核验暂存及已有 Workflow 包内 ASGI/PG18 矩阵。本项不改变业务事实、公开 API、Schema、License 或发行资格。

为避免旧候选的 21,178 文件数被误用于当前 21,182 文件候选，`tools/smoke_current_app_packaged_https.py` 将严格数量改为当前固定包并增加 Workflow START 路由文件的布局映射检查；保留原候选哈希、布局和清理护栏。脚本语法检查、错误候选定向单元 1/1 通过。随后从固定 ZIP/暂存逐件核对，在 `D:\PLMTemp` 双隔离安装布局使用包内 Python、PostgreSQL 18 和 Caddy 启动合成 HTTPS：21,185 总布局文件（载荷 21,182 加 3 元数据）、登录 200、会话 200、无 License 项目 403，错误 Host/Origin 拒绝；固定 ZIP 未改，12 个合成 Vault 密钥与数据库凭据、临时进程/目录均已清理。执行返回 `SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS`、`release_eligible=false`、`legal_clearance=false`，不含正式信任材料。

真实浏览器验收另行尝试 computer-use `node_repl` 初始化，重置会话后重试仍在任何 UI 动作前报 `failed to write kernel assets: 系统找不到指定的路径。 (os error 3)`，按工具恢复规则停止。未点击 Workflow 页面、未验证浏览器 Cookie/CSRF/首启与原操作恢复。上述外部 HTTP 仅覆盖通用登录/会话及无 License 拒绝；虽然包中 Workflow START 路由文件映射和先前包内 ASGI 矩阵已通过，本项没有经 Caddy 发起持证 Workflow GET/START，不能宣称其真实外部网络链路通过。

兼容/升级/回滚：仅更新随当前候选使用的合成烟测工具，不修改包或正式安装根，不迁移数据库；撤销工具改动即可恢复旧脚本，历史包不覆盖。正式产品 LICENSE/NOTICE、签名公钥/目标账户信任源、Server 2025/Debian 断网安装升级、浏览器、AI 质量/性能/UAT/Gate 3 仍开放。下一独立任务可在新隔离布局以合成 License 验证 Workflow 外部 HTTPS GET/START；浏览器工具恢复后再补真实 UI，不以合成结果替代发行验收。
