# PLT-PKG-01-A08-P09-P03-P01：官方 Tesseract Windows 资产固定来源

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P03-P01；仅固定并审查官方安装资产，尚不运行安装器。
- 输入基线/前置：CR-PKG-001 已先登记来源/版本偏差；旧 UB Mannheim 5.4 安装包签名无效，历史 PoC 保留。
- 模块/实体/API/权限：发行输入证据；无业务实体、API、权限、DB 或 Migration 变化。
- 验收：官方仓库/tag/资产清单与下载文件 Hash/大小一致，记录签名结果，执行本机恶意软件扫描；任何门禁失败不运行安装器。
- 风险/回滚：签名仍未有效；文件留在 Git 忽略目录，未执行/未并包，删除该精确本地资产即可撤回。

## Windows 11 结果

[Tesseract 上游官方 5.5.3 Release](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3) 提供 `tesseract-ocr-w64-setup-5.5.3.20260724.exe`；同一仓库 Release API 的资产 `digest=sha256:bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4`，大小 26,573,224 字节。本机 Git 忽略路径 `artifacts/package-prep/windows11/tesseract-ocr-w64-setup-5.5.3.20260724.exe` 下载文件大小/Hash 与 API 逐项一致。Release tag 页面标记提交者 GPG 签名验证通过，但不直接认证安装资产。

`Get-AuthenticodeSignature` 返回 `UnknownError/NotTimeValid`；签名主体 Universität Mannheim，证书于 2023-12-10 到期，时间戳证书始于 2026-06；不能宣称代码签名 PASS。Windows Defender 实时保护已启用、签名库最近更新于 2026-09-30，本机对该精确文件 `Start-MpScan -ScanType CustomScan` 返回成功且前后均未查询到该文件威胁记录；这只是本机扫描结果，不保证无恶意代码。补偿控制与剩余条件见 CR-PKG-001。

结论：`OFFICIAL_ASSET_HASH_PASS / AUTHENTICODE_FAIL / INSTALL_NOT_RUN`。本文件未执行，也未加入非发行/正式候选；正式 License/依赖清单、目标账户/Server2025、OCRmyPDF 5.5.3 兼容性和 Gate 全部待验。下一任务在隔离环境安全检查安装/解包行为，或先推进独立的受控 ASCII 模型安装与 ACL 工具；`release_eligible=false`。
