# ADR-002：Ghostscript AGPL 与源码公开策略

## Status

`ACCEPTED_WITH_RELEASE_GATE`

本 ADR 对包含 Ghostscript 的发行场景，替代 V2.1 中“GitHub 私有、源码不交付”的原发行假设；其他范围不变。

## Date

2026-09-17

## Context

项目使用 OCRmyPDF 辅助处理扫描 PDF，其 PDF/A 转换能力依赖 Ghostscript。Ghostscript 提供 GNU AGPL v3 和商业许可两种路径。原 V2.1 基线按私有仓库、源码不对客户交付设计，与采用 AGPL 路径发行 Ghostscript 的计划存在冲突。

用户已明确选择遵循 Ghostscript 开源协议，并计划在 GitHub 公开完整源代码。

## Decision

1. Phase 0 可安装和验证官方 Ghostscript AGPL 构建。
2. 项目选择 AGPL 开源合规路径，不采购商业许可作为当前默认方案。
3. 在任何包含、调用或向用户提供 Ghostscript 能力的对外发行之前，必须完成：
   - GitHub 仓库公开；
   - 项目许可证确认为与 Ghostscript AGPL v3 义务兼容；
   - 提供完整对应源代码、构建与安装资料；
   - 完成第三方许可证、版权声明和源码获取方式审查。
4. 当前私有仓库只用于开发验证，不得把“计划公开”描述为“已经完成开源合规”。
5. POC-09 / Release Gate 必须验证以上项目；未完成时不得发布包含 Ghostscript 的交付物。

## Consequences

- 可以继续验证 Ghostscript、OCRmyPDF、deskew 和 PDF/A 能力。
- 项目的源代码公开与许可证文件成为正式发行前置条件。
- 客户交付、网络服务和二进制发布范围均需纳入 AGPL 合规审查。
- 若后续不能公开完整对应源代码，应改走 Ghostscript 商业许可，并另行提交变更决策。

## Current Verification

Windows 11 已完成 Ghostscript 10.08.0 项目内免管理员安装，官方安装包 SHA-256 校验通过；OCRmyPDF 的 `--deskew` 与 PDF/A-2b 中文 OCR 链路通过。

## References

- Ghostscript 官方下载及许可说明：https://ghostscript.com/releases/gsdnld.html
- Ghostscript 官方源码仓库：https://github.com/ArtifexSoftware/ghostpdl
