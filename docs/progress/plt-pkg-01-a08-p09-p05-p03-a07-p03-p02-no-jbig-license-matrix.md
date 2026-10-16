# PLT-PKG-01-A08-P09-P05-P03-A07-P03-P02：新候选精确字节与许可定位矩阵

日期：2026-10-01；状态：`34_OF_34_BYTE_RECONCILIATION_PASS / NOTICE_RELEASE_OPEN`。编码前检查：Gate 2 已通过，Phase 2；仅新增离线证据重建工具、单元测试及 CSV，不修改正式 Parser、安装资产、ORM/Migration/API 或权限。前置为 CR-PKG-004、A07-P02 无JBIG源码构建、A06 35项旧矩阵与新34 PE静态图；旧历史文件不追写。回滚可撤本工具/矩阵，不影响候选二进制。

[34 项新矩阵](plt-pkg-01-a08-p09-p05-p03-a07-p03-no-jbig-license-evidence.csv) SHA-256 `a16312f5a322e21ad1f818fa7848a6f2b8f9f000add3b893f2b3a1e02fed15bc`。`tools/build_tesseract_no_jbig_license_matrix.py` 同时验证旧35项含 JBIG/旧libtiff、新图只有原35减去JBIG、候选文件34/34 Hash与图一致、33个非libtiff文件仍与A06包级精确字节一致。新libtiff只标 `UPSTREAM_SOURCE_BUILD`，记录上游源码tar、源码 `LICENSE.md` 固定Hash、首次输出Hash与旧MSYS2包二进制Hash不同；许可证标识仅作源文本定位、尚未分类，绝不将旧包归档/签名冒充新DLL来源。34/34 `release_obligations_reviewed=NO`。定向3项单元测试PASS，覆盖正例、篡改候选/源码拒绝、旧JBIG图拒绝。

Third Party Notices 草案取数规则：每行至少需要“组件/版本、二进制Hash、真正来源及源Hash、实际适用许可证与版权、原文文本、用户可获得对应源码与构建补丁的位置”；同一包多二进制可共享许可原文，但逐二进制来源不得丢。该 CSV 仅为来源定位，不是 NOTICE 正文、SBOM、构建签名、完整动态闭包或法律批准。对于 `PRIOR_A04_SOURCE_TEXT_REFERENCE` 的3项及包级 GPL/LGPL/双许可声明，须再次核精确源文本和适用选项；新libtiff依赖的链接库义务需独立保留。已移除的 JBIG 行不进入新候选 NOTICE，但旧候选历史仍保留。

仍缺产品 `LICENSE`/NOTICE、Ghostscript与其他 Python/前端/模型系统组件统一清单及源码交付方式、发行信任和法律复核；Windows Server 2025/正式账户、真实质量、升级JBIG格式处置及完整安装未验。该矩阵仅让发行差异可追溯，`release_eligible=false`。下一子任务单独落实 JBIG TIFF 在安装/升级前的识别与阻断/转换策略。
