# 原生 OCR 通知候选隔离 HTTPS 读链验证

日期：2026-10-01；WBS：`PLT-PKG-01-A09-P45-A06`；结果：`NON_RELEASE_NATIVE_OCR_NOTICE_LAYOUT_HTTPS_PASS`。

本项在 P45-A05 的 Windows 11 隔离布局中启动包内 API 与 Caddy，使用仅限本机回环的合成证书验证 HTTPS 读链。启动前重验新候选 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、P43/P33/P22 谱系、清洁暂存、21,161 项目标映射与全量哈希；61 条原生 OCR 许可映射仍可检索 42 份正文。映射 SHA-256 为 `9397c9891ea16840b163b8e88f5d3ef0b4aad22c2d502a0e2384667fb7d49784`。

真实进程读链返回：首页及 2 个前端资源与布局文件同字节，`/health/ready` 为 200，默认未挂载的 `/api/v1/projects` 为 404，SPA 深链为 200，错误 Host 为 421。真实脚本退出 0，子进程停止；定向单元 1/1。合成证书只证明本机网络与路由边界，不证明正式证书、目标账户、License 或生产 HTTPS 可用。

兼容性：仅 Windows 11 隔离读链；没有修改 API、Schema、Migration、SCM、正式安装根或既有数据库。升级：无迁移；终止临时子进程即可回退。`release_eligible=false`、`legal_clearance=false`、`formal_install_performed=false`。产品最终 LICENSE/NOTICE、合格法律审结、正式信任源、Server 2025 安装与 Gate/UAT 仍待；下一项在新布局用隔离数据库与合成信任材料验证登录和授权链。
