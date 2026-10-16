# PLT-PKG-01-A09-P25：新候选隔离安装布局

日期：2026-10-01；状态：`NON_RELEASE_CADDY_ISOLATED_LAYOUT_PASS / FORMAL_INSTALL_OPEN`。输入为P22固定ZIP、P23清洁暂存、P24映射及`CR-PKG-005`，无正式安装授权结论。

编码前检查：Phase2/Gate3开放，任务仅处理新非发行候选的隔离布局实证，不改业务/API/Schema/SCM/客户数据。只允许全新ASCII Temp直属目录，禁止`C:\PLMTool`写入；先验ZIP和暂存21,110载荷Hash/三清单，再复制、目标全文件集及逐件落盘Hash读回，末次复验来源。合成证书只用于临时模板语法验证，不代表客户证书/目标账户可用。

执行`tools/rehearse_windows_unified_caddy_layout.py`，输出根`C:\Users\17231\AppData\Local\Temp\plm-install-rehearsal-caddy20261001a`。固定ZIP SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`，映射SHA-256 `e30dc7732d78883c0b09be0911e0b16ade98c95b0af38008164fdc665c515ed4`；21,113个文件（21,110载荷+3清单）复制与全量回读PASS。OCR模型指纹、嵌入式Python `0.1.0.dev0`、PostgreSQL `18.6`、Caddy `v2.11.4`从隔离布局验证；包内模板在该布局的前端路径上以临时合成证书渲染并通过实际`caddy validate`。脚本exit0，定向单元2/2 PASS。首次用系统Python载入脚本时缺`cryptography`，改用固定包嵌入式运行时；其隔离导入路径不含工具目录，补显式本脚本目录导入后完整重跑PASS。上述两次前置失败均未创建输出根。

`C:\PLMTool`未创建；未注册/改动四项候选服务，未启动数据库、未运行Migration。此项只验证目标布局和模板语法，**未**从新布局进行HTTPS真实网络/登录/AI SSE或正式账户/证书测试；P23网络烟测发生于清洁解包布局。正式NOTICE/发行信任源、Server2025、Debian13（用户暂缓实机）、安装器/升级/恢复及Gate仍开放，`release_eligible=false`。下一项P26在此隔离布局做包内HTTPS静态/API/SPA及必要认证回归，之后再推进法律/安装门禁；回滚只弃用该非发行临时布局与脚本，保留P15/P22历史，不碰数据库。
