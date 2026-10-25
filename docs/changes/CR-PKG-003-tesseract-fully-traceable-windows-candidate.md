# CR-PKG-003：Windows Tesseract 同版本可追溯二进制候选

状态：`APPROVED_FOR_NON_RELEASE_POC / RELEASE_DECISION_OPEN`；日期：2026-10-01；Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A05`。依据用户 V1.1 持续授权，先记录偏差再做可撤回验证；不追写 Gate 2、POC-01 或 CR-PKG-001 的历史。

## 来源与冲突

CR-PKG-001 原优先评估 Tesseract 官方 5.5.3 Windows 安装资产。本机固定资产的静态 PE CLI 图含 33 DLL，其中 30 个与 MSYS2 官方历史包、2 个与 Debian 13 GCC POSIX 运行包精确字节匹配；`libtesseract-5.dll` 无独立精确构建包/证明，完整动态依赖与发行许可也未验。官方固定[构建脚本](https://github.com/tesseract-ocr/tesseract/blob/5.5.3/nsis/build.sh)说明两份 GCC DLL 从构建机 `/usr/lib/gcc/` 复制，但不能证明实际发布资产的构建运行；同 tag [工作流](https://github.com/tesseract-ocr/tesseract/blob/5.5.3/.github/workflows/installer-for-windows.yml)声明 Ubuntu 24.04，而两份 DLL 恰与 Debian 13 包一致，故不能据脚本或工作流推断实际构建主机。已知 Authenticode 时间链例外保持，不能冒称签名 PASS。

独立的 [MSYS2 官方 `mingw-w64-x86_64-tesseract-ocr 5.5.3-1`](https://packages.msys2.org/packages/mingw-w64-x86_64-tesseract-ocr) 发布于 2026-07-25，官方包 SHA-256 `67c0a857e9f028f88d1463c0293885d806334346a81d70be5e38f08bad11e1e3`，本机下载一致，包含 `tesseract.exe`、`libtesseract-5.5.dll`、Apache-2.0 声明及包内 LICENSE。它与原安装资产是**不同构建**，不能沿用此前 OCR、签名、质量或 DLL 清单结论。

## 方案与选择

- A：保留原官方安装资产，等待发布者提供该次构建的完整 SBOM、包清单或可复现证明。最小变化，但目前精确来源缺口使发行持续阻断。
- B（选作非发行 PoC）：从上述固定 MSYS2 包及其可逐字节归属的官方历史依赖包构造全新隔离 CLI 运行子集；重新核递归/延迟导入、包签名/Hash、许可证与通知、四版面 `--deskew`/PDF/A-2b、目标账户及 Windows 11/Server 2025。只有这些门禁和真实质量均满足后，才可单独决定是否作为 Windows 正式发行来源。该方案保持 Tesseract 5.5.3 技术栈，但二进制来源、CLI 构建、库 SONAME 与可能的 OCR 行为不同。
- C：自行从官方源码建立可复现交叉编译环境和 SBOM。来源可控，但构建/维护成本更高；B 失败或不满足安全/权利门禁时再评估。

## 差异、风险、迁移/回滚与验证

本 CR 只授权新 Git 忽略、标记 `release_eligible=false` 的隔离 PoC；不替换旧旁包、已验证模型、生产 Parser 配置或客户已安装程序。不得直接把 MSYS2 包当作发行包，也不得把 `.PKGINFO` 声明当法律结论。需要核查递归依赖与运行时动态加载、Apache/GCC/传递包许可和 GPL/LGPL 条件、训练数据/配置、缺省中文路径编码、真实质量以及离线目标环境；若有不兼容，先记录结果并调整方案。无数据库 Migration、冻结 API、产品权限或架构变化。

如果 PoC 失败，撤新候选和临时目录即可回滚，CR-PKG-001 官方安装资产与原 PoC 保留；若未来决定正式切换，须更新打包清单、Third Party Notices、安装/升级路径、版本说明及三平台验收，并提供不覆盖既有 Tesseract 安装的迁移/回退。任何安全或许可缺项都保持 Release Gate 阻断。

## 非发行验证进展

2026-10-01 A05 在 Windows 11 固定包 Hash、35 个本地 PE 静态闭包和四版面 PDF/A-2b/`--deskew` 合成术语 20/20 PASS；定向篡改拒绝和不可覆盖旧输出 2 项 PASS。详见 [A05 记录](../progress/plt-pkg-01-a08-p09-p05-p03-a05-msys2-tesseract-poc.md)。这仅满足方案 B 的第一阶段，不改变本 CR 的 `RELEASE_DECISION_OPEN`；许可/动态依赖/签名/真实质量/目标系统仍待。

2026-10-01 A06-P01 建立 35 项许可证据矩阵：32 项包内文本 Hash 重核、3 项 A04 源码文本引用，所有发行义务仍为 `NO`。详见 [A06-P01 记录](../progress/plt-pkg-01-a08-p09-p05-p03-a06-p01-license-evidence.md)；不得据此将方案 B 标记为发行许可通过。

2026-10-01 A06-P02 增加 PE 延迟导入读取，新候选 35 个 PE 延迟导入边数 0；一次中文 OCR 运行采样到随包 35/35 模块，另23个均在系统目录。详见 [A06-P02 记录](../progress/plt-pkg-01-a08-p09-p05-p03-a06-p02-delay-runtime-boundary.md)。短暂/其他输入动态加载仍未证，发行决策保持开放。

2026-10-01 A06-P03 增加可重复的 PNG/TIFF/JPEG 模块采样，三次均随包35/35、System32 23、意外路径0；系统级 ETW LoadImage 因当前非提升账户 `Access is denied` 未建立。详见 [A06-P03 记录](../progress/plt-pkg-01-a08-p09-p05-p03-a06-p03-multiformat-module-observation.md)。短时/其他格式动态加载仍阻断发行证明。

2026-10-01 A07-P01 识别 `libtiff-6.dll -> libjbig-0.dll` 的 GPL-2.0/Apache-2.0 组合风险。方案 B 的当前二进制不得直接发行，改在 [CR-PKG-004](CR-PKG-004-remove-jbig-from-windows-tesseract-candidate.md) 下评估关闭 JBIG 的同版 libtiff 隔离源码构建；原构建及历史证据不覆盖。参见 [许可风险分流](../progress/plt-pkg-01-a08-p09-p05-p03-a07-p01-license-risk-triage.md)。
