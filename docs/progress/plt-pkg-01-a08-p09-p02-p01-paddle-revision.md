# PLT-PKG-01-A08-P09-P02-P01：Paddle 模型上游 revision 锁定

## 编码前检查

- 当前 Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P02-P01，仅验证模型来源；Tesseract 安装包另项处理。
- 输入基线/前置：A08-P09-P01 的两个本地模型及复合 Hash、POC-05、CR-PAR-005；Gate 2 已通过。
- 模块/实体/API/权限：仅打包输入审计；无业务实体、API、权限、Schema 或 Migration 变化。
- 验收：固定上游 commit，对 8 个运行文件和 2 个许可声明 README 核对 Git blob/LFS oid、缓存 revision；篡改/错 revision 拒绝。
- 风险/回滚：来源证明不是目标机推理或许可法律审查；移除审计工具与本地忽略证据即可回滚，不变动模型字节。

## 来源与结果

|模型|上游固定 revision|运行文件|许可文件|
|---|---|---|---|
|[PaddlePaddle/PP-OCRv5_mobile_det](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det/tree/0d63e78e2b680928f6b1747d76a08db6e645efb7)|`0d63e78e2b680928f6b1747d76a08db6e645efb7`|4/4 Git blob/LFS oid 匹配|README 精确 Git blob 匹配，声明 Apache-2.0|
|[PaddlePaddle/PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec/tree/682f20538d8c086cb2128e5cfac775e6c4904e85)|`682f20538d8c086cb2128e5cfac775e6c4904e85`|4/4 Git blob/LFS oid 匹配|README 精确 Git blob 匹配，声明 Apache-2.0|

上游 Hugging Face 两个固定 revision 的 tree API 返回的 `oid`/LFS `oid` 与本机文件重新计算值 10/10 相同；8/8 缓存 metadata 的 revision/object id 同时匹配。模型参数 LFS SHA-256 分别为 det `afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b`、rec `2460da90875937c94db97eba74ae3d9e5d4c4c57c42f1f41531c09a26bcc771a`。审计输出位于 Git 忽略的 `artifacts/package-prep/windows11/paddle-model-revision-evidence.json`；合成正例、错 revision、篡改负例 PASS。

Tesseract [官方 Windows 安装说明](https://tesseract-ocr.github.io/tessdoc/Installation.html)指向 [UB Mannheim 发布目录](https://digi.bib.uni-mannheim.de/tesseract/)；该目录列出与本机一致的 `tesseract-ocr-w64-setup-5.4.0.20240606.exe`。本机对发布主机 HTTPS 连接超时，安装包字节/Hash/签名未取得，绝不以已安装 exe Hash 代替。下一项 `A08-P09-P02-P02` 获取并验安装包，制定受控 ASCII 路径与 ACL，再做离线安装/目标机 OCR。`release_eligible=false`；Ghostscript/PyMuPDF 法律审查、正式许可及 Gate 未通过。
