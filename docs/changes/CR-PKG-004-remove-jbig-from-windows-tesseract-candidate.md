# CR-PKG-004：Windows Tesseract 候选去除 JBIG-KIT 直接依赖

状态：`APPROVED_FOR_ISOLATED_SOURCE_BUILD_POC / RELEASE_OPEN`；日期：2026-10-01；来源：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A07-P01`。依据 V1.1 持续授权先记录后实施。该 CR 不改写 Gate 2、原官方 Tesseract 安装资产或 CR-PKG-003。

## 冲突及证据

CR-PKG-003 的新 MSYS2 5.5.3 非发行候选在 35 个本地 PE 中包含 `libjbig-0.dll`，静态 PE 图显示 `libtiff-6.dll -> libjbig-0.dll`。固定包 `.PKGINFO` 声明 `jbigkit 2.1-5` 为 `GPL-2.0`，包内 `COPYING` SHA-256 `91df39d1816bfb17a4dda2d3d2c83b1f6f2d38d53e53e41e8f97ad5ac46a0cad` 为 GPL v2 文本；[JBIG-KIT 作者项目页](https://www.cl.cam.ac.uk/~mgk25/jbigkit/)声明 GPL 软件、另有商业授权路径。当前 [MSYS2 libtiff 包](https://packages.msys2.org/packages/mingw-w64-x86_64-libtiff)将 jbigkit 列为依赖，包自身 MIT 声明不能替代依赖义务。[Apache 基金会关于 GPL 兼容性的说明](https://apache.org/licenses/GPL-compatibility.html)和 [GNU 许可兼容性说明](https://www.gnu.org/licenses/license-compatibility.en.html)指出 Apache-2.0 与 GPLv2 的组合存在兼容性问题；是否构成受限的派生/组合作品须按具体分发结构审查，不能由本项目自行宣称合规或违法。用户计划公开项目源码并不自动解决此依赖组合，且目前仓库仍为私有。

## 方案比较与选择

- A：保留官方 MSYS2 `libtiff`/JBIG，等待有资质的许可证审查或另行取得商业授权。完整编解码能力保留，但购买/签约不在 AI 授权内，当前不能据此推进发行。
- B（选作隔离技术 PoC）：从固定 libtiff 4.7.2 源码在独立构建环境关闭可选 JBIG 支持，保留其余必要编解码与 `libtiff-6.dll` ABI；验证 `libjbig-0.dll` 不再出现在静态与目标运行观察闭包，再跑 OCRmyPDF/PDF-A、TIFF/PNG/JPEG、真实质量和安全/性能回归。上游 [libtiff 构建配置](https://gitlab.com/libtiff/libtiff/-/blob/27f399af36b78aab1ff66e614b863bd0053da9f0/configure.ac)有 `--disable-jbig` 选项；对 4.7.2 精确源码/构建参数须在实施时重核。关闭 JBIG 会失去 JBIG 压缩 TIFF 支持，属于需在兼容性说明公开的范围差异。
- C：重新评估其他无 JBIG 直接依赖的 Tesseract/Leptonica/TIFF 来源或从全源码可复现构建。工作量更大，B 的 ABI/功能/安全验证失败时再比较。

选择 B 只允许 Git 忽略的隔离 PoC；不得直接替换产品 Parser、正式安装/升级包或已审计历史包。预期新 libtiff 二进制 Hash 与 MSYS2 原包不同，因此要记录源码归档、构建脚本/工具链/参数/补丁、输出 Hash、完整动态闭包、许可证与安全更新责任；所有旧 SHA 和结论保留，不冒用 MSYS2 官方包的签名/构建背书。

## 影响、迁移/回滚与验收

无数据库 Migration、冻结 API、License 机制或产品架构变化。若未来采用新构建，Windows OCR 旁包、Third Party Notices、SBOM、升级差异及 TIFF JBIG 限制需同版本更新；已有用户数据/文档中如存在 JBIG 压缩 TIFF，升级前必须识别并给出转换或阻断方案。不得静默丢弃此格式。隔离 PoC 失败则弃用新编译产物，保留原 CR-PKG-003 候选且继续阻断发行，不回滚用户数据。

实施验收：固定 4.7.2 源码与构建输入 Hash；关闭 JBIG 的实际构建日志和输出可复核；PE 普通/延迟图无 `libjbig-0.dll` 且无未解析新依赖；Windows11 与 Server2025 指定账户多格式 OCR/deskew/PDF-A、负例 JBIG TIFF、真实质量与性能；许可证/源代码/NOTICE/签名及离线安装升级 Gate。任何一项缺证不把新候选标记 `release_eligible=true`。本 CR 不是最终法律意见，法律/发行义务仍须专门核对。
