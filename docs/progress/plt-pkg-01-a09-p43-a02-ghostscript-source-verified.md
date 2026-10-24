# PLT-PKG-01-A09-P43-A02：Ghostscript 10.08.0 官方源码输入验真

日期：2026-10-01；状态：`OFFICIAL_SOURCE_INPUT_VERIFIED_NOT_BUNDLED / LEGAL_CLEARANCE_OPEN`。输入为 P33 固定非发行候选 SHA-256 `85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc`、P22 父候选以及 [Artifex 官方 10.08.0 发布资产](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/tag/gs10080)的 `ghostscript-10.08.0.tar.xz`。未改原候选。

编码前检查：Phase 2/Gate 3 未关闭；本项只验源码来源与随包版本/AGPL 文本的技术对应，不修改实体、API、权限、Schema、SCM 或安装根。前置 P43-A01 已固定官方 SHA-256；验收要求为完整归档、固定来源摘要、结构/安全路径、Windows 构建元数据、与 P33 Ghostscript `doc/COPYING` 同字节，以及明确不将技术核对写为法律放行。风险是部分下载、错误版本、归档恶意路径、把同版源码误称可重现编译。

先前普通 HTTP 下载停滞后，用 Windows BITS 新输出路径下载官方 `.tar.xz`，任务报告完整传输 69,197,208 字节；完成 BITS 交付后独立 SHA-256 为 `c20492bc8ebb96c87fa2e52a0926e1cda8cde95d66145e018ac713fed5da38cf`，与官方发布资产相同。源码位于 Git 忽略的本机 `artifacts/package-prep/windows11/ghostscript-source-10.08.0/ghostscript-10.08.0-bits.tar.xz`，未提交 Git。先前两份不完整下载仍仅为忽略区残件，不参与本次核验或发行。

新增 `tools/audit_ghostscript_source_input.py`，先独立验固定 P33/P22 谱系，再验源码字节数/摘要、9,398 个互不重复且限于版本根目录的归档项、8,681 个常规文件、无链接/特殊项、必要的 `LICENSE`、`README`、`Makefile.in`、`psi/msvc.mak` 和 Windows 项目文件。源码 `doc/COPYING` SHA-256 `57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6` 与固定候选 Ghostscript AGPL 文本一致。真实工具退出 0，状态 `OFFICIAL_GHOSTSCRIPT_SOURCE_INPUT_VERIFIED_NOT_BUNDLED`；定向单元 3/3，包括错误摘要、路径穿越及坏候选先拒绝。

结论只证明官方同版源码归档输入已取得和可追溯，不证明 Windows EXE 可重现构建、第三方子组件义务完整，也不证明对本产品的 AGPL 法律适用或发布合规。P33 无 Ghostscript 源码，`release_eligible=false`。兼容性：只增审计工具，无运行、API、Schema、Migration 或正式候选变化。升级：无。回滚：不用该本地归档/审计工具即可；P33 原 SHA 不变。下一项须先登记新候选纳入源码的包差异与验证/回滚方案，再生成并独立验真，不覆盖 P33。
