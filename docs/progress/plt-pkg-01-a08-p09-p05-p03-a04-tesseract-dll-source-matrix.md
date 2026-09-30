# PLT-PKG-01-A08-P09-P05-P03-A04：Tesseract 静态子集 DLL 来源矩阵

## 编码前检查与边界

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A04`。输入为已冻结的官方 Tesseract 5.5.3 安装资产解包及 A03 静态 PE 图；仅追溯该图的 33 个 DLL，不改变产品运行路径、安装、API、数据库或 License 机制。
- 验收口径：每个 DLL 先与官方解包逐字节 SHA-256 对账，再与官方历史 MSYS2 包内的同名 DLL 对账；包名、版本资源和软件包声明单独记录，不以同名/同版本推断字节来源或许可。只把精确匹配标为已定位候选，仍不代表完整发行合规。
- 风险/回滚：静态图不是动态依赖全集；上游资产未附精确构建时包锁；其余 DLL 和 Ghostscript/PyMuPDF 的权利链未解决。可撤新审计脚本/本地忽略候选包，原始旁包与冻结基线不变。

## Windows 11 核查结果（2026-10-01）

审计脚本 `tools/audit_tesseract_dll_provenance.ps1` 对静态图 33/33 DLL 复核官方安装资产解包 SHA，然后核对从 [MSYS2 官方历史归档](https://repo.msys2.org/mingw/mingw64/)取得的 `.pkg.tar.zst` 及包内 DLL。30/33 DLL 在历史包内找到**精确字节匹配**；其中 27 个的包内许可目录有文件，另 3 个改从同版本 [MSYS2 官方源码归档](https://repo.msys2.org/mingw/sources/) 中定位上游许可原文。其余 3 个未找到精确历史包匹配。以上均不构成发行合规结论，`release_eligible=false`。

逐项正式记录：[33 DLL 来源矩阵](plt-pkg-01-a08-p09-p05-p03-a04-dll-matrix.csv)（官方 DLL SHA、包名/版本、官方历史包归档 SHA、包声明许可、状态）、[41 条包内许可文件路径/Hash](plt-pkg-01-a08-p09-p05-p03-a04-license-files.csv)及[7 条源码许可补证](plt-pkg-01-a08-p09-p05-p03-a04-source-license-fallback.csv)。矩阵中的每个匹配包文件 URL 均为 `https://repo.msys2.org/mingw/mingw64/{package}-{version}-any.pkg.tar.zst`。本地完整机器报告为 Git 忽略文件 `artifacts/package-prep/windows11/tesseract-33-dll-provenance-a04.json`；归档二进制、许可证原文与客户数据均未提交 Git。

| 分类 | 数量 | 仍需处理 |
|---|---:|---|
| 精确包字节匹配且包内许可文本位置已找到 | 27 | 核对具体 DLL 与包内各许可/例外的适用关系，形成发行通知并审查义务；如 `libiconv`、`libintl`、`libunistring` 的多重声明不得简化为单一宽松许可 |
| 精确包字节匹配但包内无许可文本 | 3 | `libgif-7.dll`、`libidn2-0.dll`、`liblz4.dll` 的精确版本源码包 SHA、上游源码 tar SHA 与许可文本 SHA 已追溯；包内缺正文事实仍保留，发行时应携带相关上游原文并审查具体 DLL 授权范围 |
| 未找到精确包字节匹配 | 3 | `libgcc_s_seh-1.dll`、`libstdc++-6.dll` 与 `libtesseract-5.dll`；前两者与同期 `gcc-libs 16.1.0-1..5` 均不相同，官方资产文件明显更大（约 0.95/26.4 MB，对比同期包约 0.15/2.7 MB），不能借用该包的来源结论；Tesseract 官方构建配方/顶层 Apache 声明已有，但精确构建产物来源仍未证 |

排除对照：历史 `curl-winssl-8.21.0-1` 包内 DLL 与安装资产不同，`8.21.0-2` 则完全一致；两者文件版本都为 `8.21.0`，所以版本资源不能代替字节对账。普通 `libssh2-1.11.1-1/-2` 均不匹配，`libssh2-wincng-1.11.1-2` 精确匹配；包变体不能凭名称猜测。

源码补证范围：`giflib 6.1.3` 上游 `COPYING` 含 MIT 文本；`libidn2 2.3.8` 上游 README 明示库可在 GPL-2.0-or-later 或 LGPL-3.0-or-later 条款下使用，并另外提示 Unicode 数据条款；`lz4 1.10.0` 根 `LICENSE` 将 `lib/` 与其他目录区分，`lib/LICENSE` 为 BSD-2-Clause 文本。其源码包内 `PKGBUILD` 固定的上游 tar SHA 与实取文件一致。此处仅为文本/来源定位，具体再分发义务和产品许可兼容性仍待发行审查，不把包级多重声明简化成 DLL 法律结论。

验证：PowerShell 语法解析 0 错误；33/33 官方安装资产 Hash 重核；30 个精确匹配、27/3 包内许可文本分类；冻结图中 `libcurl-4.dll` SHA 篡改负例拒绝。静态 PE 图不包括延迟/动态加载、未覆盖文件格式与 NSIS 插件，不据此缩小最终许可或安装范围。

后续补齐 3 个未匹配二进制的可证来源、完整动态加载路径、实际第三方通知及 Ghostscript/PyMuPDF AGPL 与产品许可审查。没有这些证据前，不将静态子集并入可交付发行包，也不关闭 Gate 3。
