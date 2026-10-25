# PLT-PKG-01-A08-P09-P01：OCR 离线输入与候选缺项矩阵

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；非发行安装前置核查。
- 当前 WBS：PLT-PKG-01-A08-P09-P01；仅把现有 PoC 制品与本轮候选逐项对账，不宣称 OCR 离线发行可用。
- 输入基线：POC-01 Windows 11/Server 2025 OCR 链路、POC-05 Paddle 模型、A08-P07 非发行 ZIP、ADR-002 Ghostscript AGPL 路线及 CR-PAR-005 中文模型路径限制。
- 前置任务：POC 仅证明对应环境最小链路；当前候选缺系统组件，故本项限于来源/Hash/缺项证据。
- 涉及模块：本地 OCR 输入审计工具与进度证据；无解析器、实体、API、权限、Schema、Migration 修改。
- 验收标准：对已有公开制品/模型重新核哈并与候选实际内容对照，明确“开发机已安装”与“可离线部署”的差别；任一固定 Hash 不符失败关闭。
- 风险：Tesseract 离线安装包、Paddle 上游精确 revision、正式许可义务/公开源码均未收口；回滚可撤工具和 Git 忽略审计 JSON，不修改历史制品。

## Windows 11 实测矩阵

|组件|本机固定来源/验证|A08-P07 候选|待完成|
|---|---|---|---|
|Ghostscript 10.08.0 x64|POC 官方 `gs10080w64.exe` SHA-256 `52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50` 重新核对 PASS|无 `gswin64*.exe`|AGPL 分发审查、公开完整对应源码/兼容产品许可、正式离线安装|
|OCRmyPDF 17.12.1|POC 109-wheel 仓库中的 wheel SHA-256 `d1fc83dd2b567011f10afdd7612576f13c40183cbf1d867f898b64bb62d5f515` 重新核对 PASS|无 `ocrmypdf` 包；当前正式后端 93-wheel 集亦未包含|正式依赖/传递 wheel 与 deskew 编码回归、离线安装|
|Tesseract 5.4.0.20240606|开发机已装 `tesseract.exe`，版本及本机 exe SHA-256 `babb405f4366b480d02cd8ff2bac8d497170f6c1711ce6f3d5d8bf0fb7fa6ed9`；不等于安装包来源|无可执行文件|固定 Windows x64 安装包来源、Hash、许可/传递 DLL 和免管理员/管理员部署路径|
|tessdata_best|`e12c65a915945e4c28e237a9b52bc4a8f39a0cec` 提取的 `chi_sim`、`chi_sim_vert`、`eng`、`osd` 四文件按 PoC 清单 4/4 SHA-256 PASS|无模型文件|随包许可通知和目标路径/实际 OCR 验证；[上游仓库](https://github.com/tesseract-ocr/tessdata_best)声明 Apache-2.0|
|Paddle PP-OCRv5 mobile det/rec|POC Server2025 staging 两模型四个运行文件的复合 SHA-256 `511580fe3e72fe1759ce18ac05d5454eee88865303603631be644a4978889cf4`，与当前适配器算法一致；两 README 声明 Apache-2.0|无模型文件|固定上游模型 revision/下载 Hash、许可、ASCII 受控安装路径/ACL 与目标机推理；中文路径当前失败|

审计工具对候选完整性先验哈，再对上述输入逐项校验；输出在本地 Git 忽略的 `artifacts/package-prep/windows11/embedded-full-notice-candidate-ad21bbbee647/ocr-offline-input-evidence.json`，状态 `INPUT_BYTES_VERIFIED_DEPLOYMENT_INCOMPLETE`。2/2 合成测试 PASS（正确输入仍保持未部署、模型篡改拒绝）。[OCRmyPDF 官方 Windows 安装说明](https://ocrmypdf.readthedocs.io/en/stable/installation.html)也明确其系统组件需另行安装；当前候选不能把开发机 PoC PASS 继承为发行 PASS。

## 后续与 Gate

`PLT-PKG-01-A08-P09-P02` 获取并固定 Tesseract 安装包及 Paddle 模型精确上游来源，设计六组件在受控 ASCII 目录的离线安装/许可通知清单；再进行新候选装配和 Windows 11 干净目录实测。Ghostscript [官方许可说明](https://ghostscript.com/faq/)及 PyMuPDF [官方许可说明](https://pymupdf.readthedocs.io/en/latest/about.html)所涉及的 AGPL/商业双路径，按 ADR-002 的开源路线继续等待公开源码、产品许可及完整分发审查；不购买商业许可、不伪造合规结论。`release_eligible=false`，Gate 3/Release 未通过。
