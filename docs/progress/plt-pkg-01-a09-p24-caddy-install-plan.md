# PLT-PKG-01-A09-P24：新候选安装映射与服务前置

日期：2026-10-01；状态：`NON_RELEASE_READ_ONLY_CADDY_INSTALL_PLAN / FORMAL_INSTALL_OPEN`。输入为P22固定非发行ZIP（SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`）、P23清洁解包及`CR-PKG-005`。遵守ADR-013的三个固定PLM应用服务；Caddy仅为独立Web边界候选，不把应用服务数改为四。

编码前检查：Phase2/Gate3开放；本项只生成只读计划，不修改冻结业务模型、API、Schema、Migration、现有包或正式安装根。验收为固定整包/每载荷Hash、源/目标路径一一映射、Windows大小写冲突拒绝、服务职责及账户/证书来源缺口显式列出；不注册SCM，不复制到`C:\PLMTool`。安全风险为客户证书私钥及真实目标账户尚未供给，不能用合成材料代替。

`tools/plan_windows_unified_caddy_install.py`先对ZIP做固定身份/逐件验证，再把21,110项载荷与3项顶层清单精确映射到`C:\PLMTool`下21,113个目标文件，大小写冲突为0，映射清单SHA-256 `e30dc7732d78883c0b09be0911e0b16ade98c95b0af38008164fdc665c515ed4`。目标族统计：`runtime` 20,177、`app` 934、`config` 2。新增`payload/web/`→`runtime/caddy/`及`payload/third-party-sources/`→`app/third-party-sources/`；旧21,103项沿P17映射，顶层三清单→`app/package-metadata/`。示例：Caddy二进制→`runtime/caddy/caddy.exe`，模板→`config/Caddyfile.template`，可构建源码→`app/third-party-sources/caddy/buildable-artifact.tar.gz`。当前`C:\PLMTool`不存在。

服务计划只声明`PLMProjectToolApi`、`PLMProjectToolAuditWorker`、`PLMProjectToolParserWorker`三项应用服务，以及独立边界`PLMProjectToolWeb`候选。四者均`registered=false`。尚需目标账户身份/登录权/ACL/恢复策略，客户域名与匹配证书私钥来源、续期/备份、在目标账户下渲染并验证Caddyfile/Host/Origin/API回环、正式License/初始管理员仪式、PG备份迁移与服务顺序、完整NOTICE/源码法律审查和目标平台验收。无任何证书/密钥进入包或仓库。

定向单元3/3通过；固定ZIP真实计划执行exit0，`install_authorized=false`、`release_eligible=false`、`archive_extracted=false`、`services_changed=false`、`database_started=false`、`migration_executed=false`。下一项P25仅在隔离ASCII Temp布局中全量映射/Hash及包内Caddy模板烟测；正式安装及目标账户供给保留门禁。回滚删除本只读计划代码并保留历史，不涉及运行数据。
