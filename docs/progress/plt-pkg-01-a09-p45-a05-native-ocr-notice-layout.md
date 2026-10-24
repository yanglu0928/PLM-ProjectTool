# 原生 OCR 通知候选隔离布局验证

日期：2026-10-01；WBS：`PLT-PKG-01-A09-P45-A05`；结果：`NON_RELEASE_NATIVE_OCR_NOTICE_ISOLATED_LAYOUT_PASS`。

本项验证固定新候选在 Windows 11 全新 ASCII Temp 布局中的文件映射、许可材料可检索性与基本运行依赖。输入为 P45-A04 清洁暂存、固定新 ZIP SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、P43/P33/P22 谱系及 34 项 PE 矩阵。正式 `C:\PLMTool` 不存在；没有注册服务、启动数据库或执行 Migration。

在本机新目录 `plm-install-rehearsal-nativeocr20261001a` 中复制并逐项读回 21,161 个目标文件（21,158 载荷及 3 元数据），映射 SHA-256 为 `9397c9891ea16840b163b8e88f5d3ef0b4aad22c2d502a0e2384667fb7d49784`。新增原生许可正文映射到 `app/third-party-licenses/native-ocr/texts/`，审阅映射与 README 同目录；61 条记录可检索 42 份正文并再次核对 SHA-256。Go/Ghostscript 源码和许可证、OCR 模型指纹、Caddy EXE/模板及 Ghostscript EXE 身份均一致。

包内 Python 导入并输出 `0.1.0.dev0`，`pg_config` 输出 `PostgreSQL 18.6`，Caddy 输出 `v2.11.4`，Ghostscript 输出 `10.08.0`；合成证书渲染的 Caddyfile `validate` 通过。最后重验源 ZIP 和暂存目录，真实脚本退出 0；定向单元 2/2。合成证书只用于本地配置验证，未运行正式 HTTPS 服务。

兼容性：仅 Windows 11 隔离布局，未改 API、Schema、Migration、权限或 SCM。升级：无迁移；弃用隔离布局即可回退，历史 ZIP 不变。`release_eligible=false`、`legal_clearance=false`、`formal_install_performed=false`。产品最终 LICENSE/NOTICE 和合格法律审结、正式证书/公钥/账户、Server 2025 及 Gate/UAT 仍未通过。下一项验证新布局的合成 HTTPS 读链，不代替正式部署验收。
