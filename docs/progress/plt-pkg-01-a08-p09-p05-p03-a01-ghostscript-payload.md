# PLT-PKG-01-A08-P09-P05-P03-A01：Ghostscript portable 固定来源回读

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A01`；只解决 Ghostscript10.08.0 项目内 portable 目录是否逐文件来自固定官方安装资产。
- 输入基线/前置：ADR-002 的 AGPL 开源发行前置、POC-01 官方 `gs10080w64.exe` 固定 SHA-256 `52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50`、项目内 portable 解包目录与本机 7-Zip。
- 模块/实体/API/权限：仅打包来源审计工具与测试；不改业务实体、API、权限、Schema/Migration、生产依赖或系统安装。
- 验收：重新核对安装资产、CLI、`doc/COPYING` 固定 Hash；安装资产独立临时解包后与现有 portable 路径及每件字节完全一致；CLI 版本 10.08.0；篡改和额外文件拒绝。
- 风险/回滚：来源一致不等于 AGPL 发行义务已履行；旧目录/安装包不改，新增工具和 Git 忽略 JSON 可弃用。

## Windows 11 结果

官方固定安装资产独立临时解包，现有 portable 目录 654/654 文件路径与 SHA-256 一致，共 92,758,790 字节；`gswin64c.exe --version` 为 10.08.0，`doc/COPYING` 固定 Hash 对应 GNU AGPL v3 文本。按 LICENSE/NOTICE/COPYING 文件名扫描，独立通知路径仅 `doc/COPYING`；不据此推断其他组件无独立版权/通知义务。完整本机清单在 Git 忽略的 `artifacts/package-prep/windows11/ghostscript-portable-payload-audit.json`，文件 SHA-256 `3834edc84e5530f3ead4bd6d2afab0f90c10ca9935fbd0612eac2007765acf2a`。合成审计正例、CLI 篡改、额外文件拒绝 1 个测试方法 PASS。

本项结论仅为 `OFFICIAL_INSTALLER_PAYLOAD_BYTES_PASS_LICENSE_REVIEW_REQUIRED`。仓库仍私有，ADR-002 的公开完整对应源码/兼容产品许可/版权与获取方式审查没有通过；Tesseract 原生 DLL/JAR 精确来源、正式 ACL、目标系统及 Gate 仍待。`release_eligible=false`，不得因本项对外交付 Ghostscript。
