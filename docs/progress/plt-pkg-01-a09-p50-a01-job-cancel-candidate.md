# P50-A01：含项目 Job 人工取消的当前应用非发行 Windows 候选

2026-10-02 / Phase 2。编码前核查：P49 非发行打包方案和构建器、Job 取消 P01～P04、Gate 2 前置均满足；仅重建后端 wheel/前端 dist、从固定 P45 父包派生当前应用候选。无产品 API/Schema/权限/依赖变更，不碰正式安装根、服务、客户数据或既有 ZIP。发行仍受正式信任/法律/目标平台/Gate 阻断。

输入：干净 HEAD `d40441bb8d362a3058dec8b7138126d42fb17607`；固定父包 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；重建 wheel SHA-256 `afbbc6f8942d411353b9b69ad48ff5590e43ae4baf2c5370c08f0b34635d8f60`。前端生产构建产物：`index-Rd_U1OOP.js`、`index-CWhzlwuQ.css` 及 `index.html`。构建输入均来自该干净提交，本机重建不能推定跨机器可重复构建。

输出位于 Git 忽略区 `artifacts/package-prep/windows11/current-app-candidate-5fa39c2669ab/NOT-FOR-RELEASE-windows11-current-app.zip`，652,195,886 字节，SHA-256 `5fc5d8e24736d5bc2686ee8cdc105ec0eb06568d408aadf2f4cea0909f8b320d`；保留父包非应用载荷20,573项，输出载荷21,178项。manifest 仍为 `release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`。旧候选保留，不覆盖/发布；不把含未审法律材料的 ZIP 上传仓库。

验证：构建器固定父/输出全哈希与库存 PASS；清洁暂存 `D:\PLMTemp\plm-current-app-stage-p50-5fc5d8e2` 再独立全量读回21,178项，源ZIP SHA不变，退出0。前端三资产与当前dist逐件哈希一致，包内 Python `-I -B` 可导入Job取消路由和Windows写组合。首次暂存调用因工具要求目标为当前临时根直接子目录而拒绝，未创建目标；第二次仅在验证 Python 进程内指定 D 盘临时根后成功，未改系统环境。前端全量1161/typecheck/build与P03验证一致；P04包内PG/ASGI取消矩阵为旧P49包的后端执行证据，本新候选尚未再跑运行链。

迁移/升级：无本轮新增Migration，候选含既有0052；不能覆盖现有安装，正式升级仍需备份/维护/迁移/恢复演练。回滚为弃用此新候选，保留历史包。已知问题：新候选的独立HTTPS/PG运行烟测、真实浏览器、正式License/账户/产品LICENSE与NOTICE、Windows Server2025/Debian13、AI质量/性能/UAT/Gate均未关闭。下一项在隔离副本运行新候选合成HTTPS/PG Job取消链，不得冒充正式验收。
