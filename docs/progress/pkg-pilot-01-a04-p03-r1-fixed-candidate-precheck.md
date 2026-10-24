# PKG-PILOT-01-A04-P03-R1：交接修复后的非发行候选复验

日期：2026-10-24；编码前状态：`IN_PROGRESS / PILOT_NOT_READY`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `PKG-PILOT-01-A04-P03-R1`；只重建含 `HND-01-A05-A08` 修复的新非发行候选，复验原 A04-P03 Edge 入口|
|输入基线|Gate 2、CR-EXEC-002、CR-PKG-008～010；P45 固定父 ZIP SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；旧候选 SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d` 不追写|
|前置|HND 定向28、前端全量1868、类型检查与 Vite 构建 PASS；固定 pgvector wheel SHA 已由 CR-PKG-010 验证；干净提交与父包重算 SHA 后才生成新候选|
|模块、实体、API、权限|仅非发行打包/只读验收；新候选包含现有后端、前端修复、原有迁移与依赖；冻结 API、实体、权限不改|
|验收|固定来源 wheel/dist、候选清单/Hash、清洁解包；一次性合成 PG18/License/Caddy/Edge 完成登录→项目→交接/调研/需求/原型/方案/计划入口和 Workflow v1，无页面告警/网络异常；候选不变、临时 Vault/进程/目录清理|
|风险|2.2万余文件全量验证耗时；其他客户端同类 fetch 调用可能在后续功能触发。本项仅检查空白项目入口，不代替完整业务链、正式信任、离线安装升级或 UAT。|

若新候选仍失败，保持旧/新包原状并记录真实阻断；不降低验收项、不上传大体积非发行 ZIP 到 GitHub。

## 实测结果

来源干净提交 `bc97bef1309d8d36ec9af2b294e8a005432b6749`；后端 wheel 以本机无索引、无依赖下载方式构建，SHA `bd75fefb4d5f1025a03e425682dcbbf95616b3259796c741e58a1933c8547ff6`；前端全量 1868 项、类型检查及 Vite 生产构建通过。父 ZIP SHA 与固定值一致；新候选位于本地 Git 忽略区 `artifacts/package-prep/windows11/current-app-candidate-8ca6c1628399/NOT-FOR-RELEASE-windows11-current-app.zip`，654,841,731 字节，SHA `f5df4493d6c2241a882cda5b367ff69e6c80f366ed007e78ff5d5614ee61892c`，22,191 件载荷。`release_eligible=false`、`legal_clearance=false`；不上传运行包至 GitHub。

全新 ASCII Temp 暂存目录 `C:\Users\17231\AppData\Local\Temp\plm-current-app-stage-a04p03r1x24` 清洁解包/逐项读回 22,191 件通过；包内前端 `index.html` SHA 与新 Vite dist 完全一致。固定新候选再次经过两份 22,194 件布局、包内 PG18/API/Caddy、合成 Ed25519 有效 License 与 HTTPS：错误 Host/Origin/未授权 Project 拒绝，登录/会话 200；Workflow GET v0、START v1、重放/CSRF/冲突/单 Audit/收据通过。

真实 Edge 从新浏览器配置登录，访问自己的项目详情，逐一打开交接、调研、需求、原型、方案目录、实施计划入口，均无可见告警；Workflow 显示并刷新为 `ACTIVE/HANDOVER/v1`。浏览器共观察到 17 个 API 响应，无非 2xx、加载失败或脚本异常；交接页在旧包中发请求前失败，新包中已正常读取。截图仅在内存求 SHA `76f6ced1280e76ff1eae44e6cb0a9b16a57f2be8d033e699b7822eae8f63e44d`，未保存客户资料或运行产物。验收器退出0，结果 `SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS` 且浏览器固定标记 `PKG_PILOT_01_A04_P03_EDGE_PASS`。

验收后候选 SHA 未变，48 个临时 Vault 引用为0残留，临时安装布局为0，包内进程停止。清洁暂存目录作为下一项只读验证输入保留；旧失败包也保留。正式发行公钥、操作员签发、真实服务账户/CA、法律放行、离线安装/升级、完整业务数据链/UAT和 Gate 尚未通过，Pilot 仍 `NOT_READY`。本项的六个入口只证明空白合成项目的页面与只读端点可用，不证明客户事实或业务成果已生成。

Changed：从固定提交重建独立非发行候选，复验真实 Edge；无新产品代码。Files：本证据，忽略区新候选/暂存；Migration/API/权限：无变更。Tests：定向28、前端全量1868/typecheck/build、包清洁解包、包内 HTTPS/License/Workflow、Edge 六入口及 Workflow PASS。Result：`SYNTHETIC_PACKAGED_EDGE_ENTRY_PASS / PILOT_NOT_READY`。Known Issues：完整业务写链、正式信任/法律、安装升级/备份/UAT/Gate未验。Next：`PKG-PILOT-01-A04-P04` 在新包内实测从浏览器创建项目的写链，再逐项推进交接等业务结果。
