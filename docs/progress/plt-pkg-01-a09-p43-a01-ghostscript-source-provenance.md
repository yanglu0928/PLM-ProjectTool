# PLT-PKG-01-A09-P43-A01：Ghostscript 对应源码来源固定与取得状态

日期：2026-10-01；状态：`OFFICIAL_SOURCE_IDENTITY_PINNED / ARCHIVE_NOT_ACQUIRED / LEGAL_CLEARANCE_OPEN`。本项只确认 P33 非发行候选所用 Ghostscript 10.08.0 Windows x64 二进制的同版本官方源码出处，不变更候选、安装或许可证结论。

编码前检查：P28 已确认候选仅含 Ghostscript `doc/COPYING`，未定位对应源码；P43 不触碰业务/API/Schema、正式根或客户数据。验收是来源、版本、文件名、官方 SHA-256 与现有二进制输入建立可追溯关系，且只有完整下载并校验相符才可把“源码已取得”记为 PASS。

Artifex [Ghostscript 发布页](https://www.ghostscript.com/releases/gsdnld.html)把 10.08.0 的 Windows 64 位版和全平台源码列为 AGPL 发行输入；[官方 GitHub 10.08.0 发布资产](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/tag/gs10080)列出 `gs10080w64.exe` SHA-256 `52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50`，与本项目现有固定安装器常量一致，并列出 `ghostscript-10.08.0.tar.gz` SHA-256 `caf199e3f233f1290b27d0972d636f66c303355f2353309b7bfddf1edda06b3d`、`ghostscript-10.08.0.tar.xz` SHA-256 `c20492bc8ebb96c87fa2e52a0926e1cda8cde95d66145e018ac713fed5da38cf`。这固定了推荐的同版源码输入，但尚未证明官方 Windows EXE 与任一源码压缩包的构建字节可重现，也不证明对应源码法律义务已履行。

尝试将官方 `.tar.gz` 下载至 Git 忽略的本机 `artifacts/package-prep/windows11/ghostscript-source-10.08.0/`：约 383.8 KiB 后连接吞吐停滞；尝试第三方镜像的 `.tar.xz`：约 24 KiB 后同样停滞。两个传输均主动中断，均不是完整归档，**不得校验为 PASS、入候选或用于发行**。这两个不完整文件位于 Git 忽略区，未加入版本库；自动清理命令被当前命令执行策略拒绝，故保留为明确未验证的本机残件，不把它们当成果。下一次获取必须采用全新输出路径，完成后用官方 SHA-256 校验，检查归档结构及 `doc/COPYING`，再决定是否纳入新的非发行候选；原 P33 不覆盖。

Artifex 的[许可说明](https://artifex.com/licensing)称 Ghostscript 同时提供 AGPL 与商业许可，并就其所述的服务/集成场景强调源码披露要求。这里仅记录供应商原文所表达的发行风险，不替代有资质的法律审查，也不自行断言本产品公开仓库已满足 AGPL。产品级 LICENSE/NOTICE、对应源码提供方式、第三方组件逐项义务以及发布前法律复核仍为 `REVIEW_REQUIRED`；`release_eligible=false`。

兼容性与升级：纯来源证据，无运行变化或迁移。回滚只需不采用本次建议的源码输入；现有 P33 与 P42 证据不变。后续 P43-A02 在可用下载渠道取得完整源码并独立验真，同时推进其他不依赖该下载的许可清单工作。
