# CR-PKG-001：Windows Tesseract 离线发行来源调整

状态：OPEN / SOURCE_PINNED_SIGNATURE_EXCEPTION_UNDER_REVIEW；日期：2026-10-01；Phase 2 / PLT-PKG-01-A08-P09-P03。Gate 2 技术栈 Tesseract 不变；本 CR 仅调整 Windows 离线发行二进制的来源/版本，不追写 POC-01 或 ADR-001 的 5.4 历史验证。

## 来源、冲突与方案

POC-01 使用 UB Mannheim Tesseract 5.4.0.20240606；其 [发布者 Release](https://github.com/UB-Mannheim/tesseract/releases/tag/v5.4.0.20240606) 下载件 50,175,248 字节/SHA-256 与 [Microsoft winget 固定清单](https://github.com/microsoft/winget-pkgs/blob/master/manifests/u/UB-Mannheim/TesseractOCR/5.4.0.20240606/UB-Mannheim.TesseractOCR.installer.yaml) 一致，但本机 Authenticode 报证书超期，链验证 `NotTimeValid`。来源 Hash 匹配不等于有效签名；该文件未执行或并入候选。

- A（选定）：评估 [Tesseract 上游官方 5.5.3 Release](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3) 的 Windows x64 安装资产。先核来源、固定 Hash、签名、许可和传递 DLL；若安全门禁通过，再在隔离 Windows11 路径重新验证 OCRmyPDF/deskew/中文训练数据与 Parser；最后做目标账户/Server2025。版本升级不能继承 5.4 的 PoC PASS。
- B：继续使用 5.4 历史安装资产，基于发布者 Release 与独立固定 Hash 作为替代控制接受过期签名。风险是代码签名身份不能有效验签，须另行记录安全例外和隔离测试；当前不选。
- C：自行从官方源码构建 Windows 二进制。来源可控，但编译环境/依赖与再现性成本更高；作为 A 失败时的后备方案，不预先实施。

## 差异、影响、迁移/回滚、验证

原历史 5.4 PoC、已安装开发机程序和非发行候选保持不动。若 A 通过，发行包固定 5.5.3 x64 及其 Hash/许可证，并在目标部署中作为新系统依赖；不自动升级或覆盖用户机器已有 Tesseract。若验证失败，拒绝并包，保留 5.4 PoC 与现有安装，回滚仅撤新候选与测试目录，不回滚业务数据库。

验证顺序：上游资产清单 → 下载字节/Hash/Authenticode → 许可/原生依赖清单 → 隔离安装及版本、tessdata_best 中英/OCRmyPDF `--deskew` 中文 Windows 输出编码 → 与 Ghostscript/Paddle 的合成 OCR 链 → Windows11/Server2025 清洁目标目录与账户 ACL/离线复装 → 发行安全与许可审查。未经过对应阶段不得宣称兼容或 Release PASS。无 DB/API/产品权限变化；可能改变 OCR 结果，需记录质量回归。旧候选始终 `release_eligible=false`。

## 2026-10-01 上游资产核查及安全差异

官方 5.5.3 GitHub Release API 登记 Windows 安装资产 `tesseract-ocr-w64-setup-5.5.3.20260724.exe` 26,573,224 字节、SHA-256 `bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4`；本机下载字节逐项相同。Release tag 页面显示提交者 GPG 签名已验证，但 Git tag 签名不直接签署二进制。该资产 Authenticode 也返回 `UnknownError/NotTimeValid`：与 5.4 相同的 Universität Mannheim 签名证书 2023-12-10 到期，而时间戳证书起于 2026-06。不能把它写成有效代码签名。

修订选择：仍优先 A 的官方 5.5.3，但将官方 Release API 的资产 digest 固定校验、HTTPS 来源、仓库/tag 身份、当地 Defender 扫描和隔离目录实测作为**替代来源控制**，不是 Authenticode PASS。先执行非生产隔离验证；若 Defender、文件清单或运行异常，立即拒绝。发行并包前还须完成许可/传递依赖、目标环境和专项安全评审；未满足即维持 `release_eligible=false`。B 的第三方 5.4 包不再作为优先候选，C 自行构建保留为后备。撤销替代方案只需删除未发行候选/测试目录，不动既有程序或数据库。

## 2026-10-01 中文绝对路径复验差异

官方 5.5.3 解包 CLI 在中文仓库路径下 `--version` 与短图像 OCR 成功，但将同路径下 `tessdata_best` 提供给 OCRmyPDF17.12.1 的 PDF/A-2b、`--deskew` 合成链时，Tesseract 语言列表探测报 `filesystem error: Cannot convert character sequence: Illegal byte sequence`，OCRmyPDF exit 3。当前不能判定是 exe、tessdata、子进程传参或环境变量的哪一段非 ASCII 路径触发；不继承 5.4 PoC 的 deskew PASS。

所选诊断/调整：在不改 OCRmyPDF/冻结 API 的前提下，分别对 exe 和 tessdata 做固定 Hash 的 ASCII 测试路径对照；若证实路径约束，正式 Windows 发行的 OCR 系统组件与模型都须置于受控 ASCII 目录并限制普通用户写入，配置启动时失败关闭。复制仅限 Git 忽略的合成隔离目录，原安装、旧 PoC 与数据库不变；失败可撤隔离目录。必须重跑语言列表、PDF/A-2b/deskew、中文术语与目标账户/Server2025，不把短图像 OCR 当完整链路。

## 2026-10-01 同条件 OCR 质量回退

将固定 tessdata_best 四语言数据放到 ASCII 目录后，5.5.3 语言探测恢复；再补安装包自带 `configs`、`tessconfigs` 和 `pdf.ttf`，OCRmyPDF17.12.1 `--deskew` + Ghostscript10.08.0 的 PDF/A-2b 执行 exit 0。然而原 PoC 五个术语中标题最后一个“具”识别成“只”，仅 4/5；用**同一** ASCII tessdata/配置、脚本、字体、合成 PDF 及其他依赖切回本机 5.4，5/5 PASS。此为当前固定样本的可复现版本质量差异，不代表广义中文准确率结论。5.5.3 不能凭“流程跑通”继承 5.4 的质量验收。

调整验证计划：先在不更换模型、不放宽 5/5 门槛的前提下比较 5.5.3 的 PSM/OEM 等小范围配置；若不能稳定达到旧版样本与后续独立样本门槛，不选 5.5.3 发行。选回 5.4 时须单独权衡旧版安全修复缺口及 Authenticode 例外；官方 5.5.3 的后续安全修复不能忽略。未完成安全和质量双门禁时维持 `release_eligible=false`，不默认选容易通过的窄方案。

参数对照已完成：5.5.3 的 PSM3/4 在旧合成页 5/5，PSM6/11 为 4/5，全部 PDF/A-2b/deskew exit0；5.4/PSM6 同条件 5/5。旧默认仍保留；不能基于一个页面选生产 PSM，需要独立多版面/低质量样本与人工标签回归。中文路径错误进一步定位为 tessdata 绝对路径，ASCII 模型仅复制 `.traineddata` 又缺 `configs/hocr`；正式离线装配必须包含运行配置并限制目录写权限。

独立合成版面扩展为标准/密集/表格/轻微倾斜四类；5.5.3/PSM3 全部 5/5，5.5.3/PSM4 在表格 4/5，旧 5.4/PSM3 在表格亦 4/5。推荐 5.5.3/PSM3 进入后续候选，但未改默认或宣称正式质量验收；需有真实低质/复杂客户类文档的本地、人工标注回归及发行安全/许可门禁。固定来源精确依赖版本仍缺 2026-07 构建包清单，单独保留阻塞。
