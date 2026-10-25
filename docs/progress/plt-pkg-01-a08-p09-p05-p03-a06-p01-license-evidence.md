# PLT-PKG-01-A08-P09-P05-P03-A06-P01：MSYS2 候选许可证据定位

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A06-P01`；仅为 A05 新候选的 35 个本地 PE 建立可复核的许可文本定位表，不判断发行权利。
- 输入基线/前置：CR-PKG-003、A05 固定包清单和静态图、A04 33 DLL 来源/包内许可/源码文本矩阵。Gate 2 已通过；Gate 3 未通过。
- 模块/实体/API/权限：新增离线审计工具、定向测试和 CSV；无产品程序、ORM、Migration、API、权限、正式安装或发行清单变化。
- 验收：35/35 二进制文件 Hash/包归档 Hash 与 A05 清单一致；A05 清单与静态图一致；每项定位包内或 A04 已登记的源码许可文本证据；明确记录与旧官方安装资产的字节差异和待法律/发行审查状态。
- 风险/回滚：包 `.PKGINFO` 的许可声明不是具体二进制的法律结论；源码文本引用尚未在本项重新解包复核；运行时动态加载可能引入更多组件。可撤新工具/矩阵，A05 PoC 和原安装资产不变。

## Windows 11 结果（2026-10-01）

[35 项证据矩阵](plt-pkg-01-a08-p09-p05-p03-a06-msys2-license-evidence.csv)由 `tools/audit_tesseract_msys2_license_evidence.py` 从 A05 本机忽略 `manifest.json` 与静态图、固定 MSYS2 包归档、A04 历史矩阵重建。复核输出与提交 CSV SHA 完全相同；35/35 包内二进制 Hash 与清单一致、包归档 Hash 与固定值一致、静态图无多余 DLL。A04 官方安装资产对照：30 项字节相同；`libgcc_s_seh-1.dll`、`libstdc++-6.dll` 两项不同；新增 `libgomp-1.dll`、`libtesseract-5.5.dll`、`tesseract.exe` 三项。

32 项定位并重核包内许可文本 Hash（旧候选相同的27项、新 GCC 3 项及 Tesseract 2 项），另3项 `libgif-7.dll`、`libidn2-0.dll`、`liblz4.dll` 仅承接 A04 的固定版本源码文本路径/Hash，标为 `PRIOR_A04_SOURCE_TEXT_REFERENCE`，未在本项重复核源归档。GCC 包声明含 GPL-3.0-or-later WITH GCC-exception-3.1 与 LGPL-2.1-or-later，Tesseract 包声明 Apache-2.0；均仅如实记载 `.PKGINFO`，未确定各文件适用关系或产品分发义务。所有 35 行的 `release_obligations_reviewed=NO`。

定向测试2项 PASS：完整合成清单可生成非发行矩阵，静态图不符或许可文本缺失会拒绝。正式法律/许可审查、所需源代码/通知交付方式、包签名、动态导入、真实质量和目标账户/Server2025 尚未通过，`release_eligible=false`。A06 下一子项核延迟导入及显式动态加载边界；许可证义务与 Third Party Notices 仍是独立发行阻断，不能因本表关闭。
