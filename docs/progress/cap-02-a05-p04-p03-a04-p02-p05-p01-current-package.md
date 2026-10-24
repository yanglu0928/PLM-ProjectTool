# CAP-02-A05-P04-P03-A04-P02-P05-P01：当前源码非发行包内前置

日期：2026-10-24；状态：`CURRENT_CANDIDATE_PACKAGED_BASELINE_PASS / REVIEW_PACKAGED_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A04-P02-P05-P01`；只核对当前已提交源码的非发行 Windows 11 候选及基础包内启动/能力基线链。|
|输入基线|`CR-EXEC-002`、`CR-CAP-005/006`、Gate 2 原冻结提交；源提交 `2caf17525e050378dd6b25b667cc6ae930263da1`。|
|前置|A03-P01 前端全量1947/typecheck/build，A03-P02 Edge/隔离PG已通过；P45 父 ZIP SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f` 均重算一致。|
|模块/实体/API/权限|本片不改产品代码、Schema、API、权限；重建 wheel、前端 dist、非发行派生 ZIP，运行既有包内验收。|
|验收|干净提交、逐件 Hash、清洁解包、包内 Python/PG18/API/Caddy/HTTPS/License/Edge 的合成来源→基线身份链、拒绝和清理。|
|风险|655MB ZIP 和 22,196 件载荷导致全量核验较慢；此片不证明新 Review UI/决定在包内通过，也不证明正式信任/法律/安装/UAT。|

Python 3.13 本机无索引、无依赖下载构建后端 wheel，SHA `4215c32553502cf3798db8d65385b0b6afe1f29791b012271091e9315015eb62`；前端类型检查/生产构建通过。新 ZIP 位于 Git 忽略区 `artifacts/package-prep/windows11/current-app-candidate-df763d07a37e/NOT-FOR-RELEASE-windows11-current-app.zip`，654,894,973 字节，SHA `f2a2385538b111a1a36e3761086e0f4e5749554a3c57bde8941c0fb11080e095`，载荷 22,196 件。候选与父包各自保留，`release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`；不上传大 ZIP 到 GitHub。

在全新直接 ASCII 临时目录 `D:\PLMReviewTemp\plm-current-app-stage-capreviewp05x24` 清洁解包并逐件读回，脚本退出0；另两份临时布局的 22,199 件映射和哈希通过。包内合成 License/登录、未授权 Project 403、Workflow HTTPS GET/START/重放/CSRF/冲突/Audit、真实 Edge 合成 GLOBAL 来源上传→AVAILABLE 固定版本→能力基线身份创建及 PG 四类 Audit 均退出0。候选 SHA 前后相同；48 个合成 Vault 目标已清空，PG/API/Caddy/Edge 进程和两份临时布局已清理。

这仅关闭“当前代码已进入可启动候选包”的前置，不关闭固定版本评审的包内正负链。清洁暂存目录保留供下一片只读复用。正式公钥/真实服务账户/法律结论、离线安装/升级、真人确认、Server2025/Debian13、Gate/Pilot/Release 仍未通过。下一任务 `P05-P02` 在同一固定 SHA 上验收普通评审人包内固定内容/决定与拒绝矩阵。
