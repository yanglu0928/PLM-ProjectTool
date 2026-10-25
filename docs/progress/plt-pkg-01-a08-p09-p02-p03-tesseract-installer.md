# PLT-PKG-01-A08-P09-P02-P03：Tesseract 安装包来源与签名核查

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P02-P03；只核对系统组件来源、字节与签名，不执行安装。
- 输入基线/前置：P09-P01 已安装 Tesseract 5.4.0.20240606 仅有 exe Hash；Tesseract 官方 Windows 安装页指向 UB Mannheim；A08-P09-P02-P02 ASCII 模型 OCR 已实测。
- 涉及模块/实体/API/权限：离线打包输入证据；无产品程序、业务实体、API、数据库、权限或 Migration 变化。
- 验收：发布者资产与独立包管理器清单一致、文件 SHA-256/大小准确、签名状态明确；不以网页或旧系统 exe 代替安装包验收。
- 风险/回滚：安装包 Authenticode 未通过，不允许执行/并入发行候选；本地文件在 Git 忽略目录，可按固定文件目标撤销，既有候选不变。

## 实测

来源：[UB Mannheim v5.4.0.20240606 Release](https://github.com/UB-Mannheim/tesseract/releases/tag/v5.4.0.20240606) 的 `tesseract-ocr-w64-setup-5.4.0.20240606.exe`；[Microsoft winget 对应安装清单](https://github.com/microsoft/winget-pkgs/blob/master/manifests/u/UB-Mannheim/TesseractOCR/5.4.0.20240606/UB-Mannheim.TesseractOCR.installer.yaml) 登记同一发布资产及 SHA-256。原 Mannheim 下载主机本机 TCP 443 超时，故改从同一发布者 GitHub Release 获取。

- 本地 Git 忽略路径：`artifacts/package-prep/windows11/tesseract-ocr-w64-setup-5.4.0.20240606.exe`。
- 大小：`50,175,248` 字节，与发布者 GitHub API 资产大小一致。
- SHA-256：`c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9`，与 Microsoft winget `InstallerSha256` 一致。
- Windows `Get-AuthenticodeSignature`：`SignatureType=Authenticode`，签名主体 Universität Mannheim，但 `Status=UnknownError`；状态消息为证书在当前系统时钟或签名时间戳下不在有效期。签名证书有效期 2022-12-09 至 2023-12-10，发布资产日期 2024-06。禁用吊销检查的证书链验证也因 `NotTimeValid` 失败。此结果不等于已验证发布者签名。

结论：`SOURCE_BYTES_PINNED_SIGNATURE_NOT_VALIDATED`，不是安装 PASS。文件未执行、未并入候选。若后续依据发布者资产 + 独立固定 Hash 接受该历史签名瑕疵，须先登记可追溯安全偏差和替代控制，再做隔离安装/运行/许可检查；也可选有有效签名的其他正式来源，但任何版本替换必须重新固定来源并复验 OCR。不能静默忽略签名错误。`release_eligible=false`。
