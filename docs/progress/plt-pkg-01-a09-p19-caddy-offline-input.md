# PLT-PKG-01-A09-P19：Caddy Windows 离线输入固定

日期：2026-10-01；状态：`PINNED_OFFICIAL_INPUT_PASS / HTTPS_INTEGRATION_OPEN / NOT_RELEASE_READY`。追溯：`CR-PKG-005`、DEC-566、P18-A03。此项只固定外部边界的 Windows AMD64 官方输入，不将其加入旧 P15 组合包。

## 编码前检查

|项|结果|
|---|---|
|当前 Phase / WBS|Phase 2 / PLT-PKG-01-A09-P19；Gate 3 开放。|
|输入基线 / 前置|Gate2 冻结架构、ADR-013、P18-A03 部署缺口、先行 `CR-PKG-005`/DEC-566。|
|模块 / 实体 / API / 权限|仅非发行离线输入审计工具；无业务模块、实体、API、权限或 Migration 变化。|
|验收标准|官方固定版本/四资产 SHA-256 与发布 SHA-512、ZIP 内 EXE/许可、源码归档、SBOM 身份一致；拒绝变更输入；不安装服务、不提升发行资格。|
|风险|官方资产真实性不等于全部三方依赖许可审查、TLS/Host/Origin 服务安全或目标平台验收。|

官方 `v2.11.4` 发布的 Windows AMD64 ZIP、CycloneDX SBOM、含 `vendor/` 的 buildable source tarball、checksums 取自[发布页](https://github.com/caddyserver/caddy/releases/tag/v2.11.4)并暂存于本机忽略范围 Temp，不入 Git。发布 API 提供的 ZIP SHA-256 为 `1708333f79e274c7697285afe6d592ab39314e0b131e9ec6bea08ad27df62ebf`；本地逐件 SHA-256 及官方 checksum 文件中的逐件 SHA-512 一致。ZIP 仅 `caddy.exe`、`LICENSE`、`README.md`；EXE SHA-256 `5cb9ab71e5756ce72840b8234177a2f40c8b4ab47a806b8e841e2b784e9df62b` 与 SBOM 元数据相符，隔离执行 `caddy version` 返回 `v2.11.4`。ZIP 与源码归档的 `LICENSE` 文本 Hash 一致，文本为 Apache License 2.0。SBOM 含 149 个组件；各下游义务尚未逐一审查。

新增 `tools/audit_caddy_windows_offline_input.py` 只读固定四资产、发布 SHA-512、严格 ZIP 成员、EXE/许可、源归档核心文件及 SBOM 身份，结果写入新的本机审计 JSON；重跑不能覆盖既有结果。单元 3/3 PASS；真实四资产审计 `PINNED_OFFICIAL_INPUT_PASS_NOT_RELEASE_READY`，审计 JSON SHA-256 `25b75ae5fb053c7e46d421b78ec391e2ed5a1c4f2ca56e5ccc68fdc35a9d6a46`。未修改 `C:\PLMTool`、SCM、数据库、原 ZIP 或正式证书；`release_eligible=false`。

下一步 P20 以合成证书和隔离回环端口进行 HTTPS 同源静态/REST/SPA/SSE/安全拒绝 PoC，再决定新发行候选装配。客户证书/ACL、完整许可 NOTICE、Windows Server 2025 与 Debian 13、正式登录/业务 UAT、Gate 3～7 仍开放。可撤销审计工具和非发行候选，不改 P15 原历史。
