# 原生 OCR 许可材料新非发行候选

日期：2026-10-01；WBS：`PLT-PKG-01-A09-P45-A03`；状态：`NON_RELEASE_NATIVE_OCR_NOTICE_INDEPENDENT_VERIFY_PASS`。

## 输入与偏差

本项按 [CR-PKG-007](../changes/CR-PKG-007-native-ocr-license-sidecar-candidate.md)执行。输入为固定 P43 候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、P33/P22 谱系、34 项原生 PE 矩阵及从精确原始归档核实的 61 条许可文本。P43 历史 ZIP 不改，原冻结架构、API 与 Schema 不变。

## 产物与证据

新 ZIP 位于本地 Git 忽略区 `artifacts/package-prep/windows11/unified-native-ocr-notice-candidate-b3f6c6b387be/NOT-FOR-RELEASE-windows11-unified-pg18-caddy-go-ghostscript-native-ocr-notices.zip`，仅供审阅，不上传大体积运行物。大小 652,122,261 字节，SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`。它保留 P43 的全部 21,114 项载荷且逐项哈希一致，并新增 42 个以正文哈希命名的文本、61 条逐二进制/来源映射及 README；载荷总数 21,158。

构建器完成 ZIP 全量清单/哈希核对；独立核验器再次核对 P43/P33/P22 谱系、34 项 PE、61 条映射、新 ZIP 全部文件及发行门禁，真实运行退出 0。构建器与核验器的定向单元分别 3/3 和 3/3。映射是技术审阅材料，不将 `release_obligations_reviewed=NO` 推定为已审结。

`release_eligible=false`、`legal_clearance=false`、`installation_performed=false`、`service_registration_performed=false`。本项未清洁解包、正式安装或注册服务，也未取得合格法律意见。产品级最终 LICENSE/NOTICE、正式信任源、Server 2025 安装和 Gate/UAT 仍开放。下一项 P45-A04 在全新 ASCII 临时目录清洁解包并逐项读回，不改变发行门禁。回滚方式为弃用新候选，保留 P43 固定历史包。
