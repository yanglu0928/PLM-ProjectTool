# WFL-01-A08-P05：当前 Workflow 非发行候选一致性/随包运行

2026-10-02 / Phase 2 / `NON_RELEASE_PACKAGE_SMOKE_PASS`。打包前检查：干净提交 `71375e9f6425afb0f8a8ce9b0dfc8580aaf808cf`、固定父包 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、前端61文件1194测试/typecheck/build、后端1830测试/3跳过，以及原非发行派生构建器和一体化迁移工具均可用。只在本地 Git 忽略区创建新候选与 D 盘一次性校验暂存；不覆盖旧包、正式安装根、服务或客户数据库。法律/正式信任/Gate 阻塞不因本项解除。

从当前提交重建后端开发 wheel，SHA-256 `0a8bd6afbb2529c84bceea33b4c11a7532f7fbd5472aab756175228a3ccaf45d`；前端 dist 为 `index-BfIr0e3P.js`、`index-DenW7eyR.css` 和 index.html。工具按父包清单保留非应用第三方/运行时20,573项，仅替换后端 wheel 与前端 dist，生成本地忽略区 `artifacts/package-prep/windows11/current-app-candidate-8a632087b024/NOT-FOR-RELEASE-windows11-current-app.zip`，652,207,678字节，SHA-256 `6b0cd4978d5526554443d6ab1b0528ddd4c2feebfa7690c41af627fe55887acb`；载荷21,182项。manifest 明确 `release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`。旧候选保留；不将尚未法律放行的 ZIP 上传仓库。

验证：构建器定向3项及固定父包/输出全哈希 PASS；独立清洁解包到 `D:\PLMTemp\plm-current-app-stage-wfl-6b0cd497` 后逐件21,182文件/元数据全哈希与全集 PASS，ZIP 重新 SHA 不变。包内关键 Workflow 路由/服务/Windows组合与当前源码、前端三资产与当前 dist 逐件同字节；编译 JS 含 `workflow:start`、项目流程/原操作提示；包内 Python `-I -B` 导入 Workflow/组合成功。再用**包内 Python 与 PostgreSQL 18.6**运行 `validation/wfl-01-a06-p04-platform-start/verify.py`，真实隔离库/Session/CSRF 下首次/重放/经理权限/合成 License/缺信任源双显式平台矩阵 PASS；默认/login-only关闭、无 Gate/StageTransition。临时 PG 停止并清理，55432无监听。首次打包未报错；当前候选不是正式安装器，也未做真实浏览器点击或外部网络 HTTP。

兼容/升级/回滚：新增前端路由与后端受控启动已在上述历史任务记录，候选沿用至0052 Schema，无本项新 Migration。此项不对现有数据升级；正式升级仍需人工备份、维护、迁移及恢复演练。回滚是弃用本地新候选并保留旧包/来源提交；若真实 Workflow 已启动，其 Audit/收据不能随文件回滚。产品级 LICENSE/NOTICE、正式签名公钥/目标账户密钥、Server2025/Debian断网安装升级、真实浏览器、AI质量/性能/UAT/Gate3～Release未通过；禁止将该 ZIP 交付为正式可使用程序包。
