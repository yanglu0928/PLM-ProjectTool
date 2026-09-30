# PLT-PKG-01-A08-P09-P05-P02-A01：后端与 OCRmyPDF 联合离线轮子

## 编码前检查

- Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P02-A01`；正式 ACL 子项独立阻塞，不影响此隔离构建。
- 输入：A01 后端 93-wheel 固定清单、P05-P01 OCRmyPDF 26-wheel 固定清单、CR-PKG-002 的唯一 `charset_normalizer` 3.5.2/3.5.1 冲突。
- 受影响范围：仅 Git 忽略的 Windows 非发行 wheelhouse 和构建/校验工具；不改正式后端依赖、实体、API、权限、Schema 或 Migration。
- 验收：双方来源逐件 Hash；只接受 CR 已记录的唯一冲突且保留后端 3.5.2；新输出 106 wheel 再验 Hash；全新 Python3.13 x64 venv 无索引同时安装产品后端和 OCRmyPDF、`pip check` 与版本/导入。
- 风险/回滚：联合 Python 包成功不证明嵌入式发行或 OCR 系统组件。旧 wheelhouse/候选均保留；可弃用新输出并撤独立工具。

## Windows 11 结果

- 93/93 后端来源和 26/26 OCR 来源 Hash 复核；仅有 `charset_normalizer` 一处版本冲突，按 CR-PKG-002 保留后端固定 3.5.2，补入 OCR 原缺 13 wheel。输出为 106 wheel，清单 SHA-256 `49ee7bf0d154b423dbbedbf330ee989a41f23cbc459c8670a97bd7da753d16f8`，位于 Git 忽略的 `artifacts/package-prep/windows11/combined-ocr-20261001-032638-37f3ac3c`。
- 全新 Python3.13.15 AMD64 venv 从联合 wheelhouse `--no-index` 同时安装 `plm-project-tool-backend==0.1.0.dev0` 与 `ocrmypdf==17.12.1`，`pip check` 无损坏依赖；产品、PaddleOCR、OCRmyPDF、pikepdf 导入及 `charset-normalizer==3.5.2` 断言 PASS。
- 输入根越出受控 `artifacts/package-prep/windows11` 的负例在任何复制/安装前拒绝。未执行真实 OCRmyPDF PDF/A 命令、嵌入式 Python 合并、物理断网或服务账户 ACL；不以本项关闭 P05-P02 整体。

## 下一子项

以固定 106-wheel 联合来源重建新的非发行嵌入式运行时，并核验私有 `sys.path`、106 项发行元数据、原生 DLL、OCRmyPDF CLI 与已固定 Tesseract/Ghostscript/tessdata 的合成 PDF/A-2b/`--deskew`。CR-PKG-002 保持 OPEN 至此链路实测；Tesseract 精确原生来源/签名/许可、AGPL、正式 ACL、真实质量及目标系统/Gate 仍待，`release_eligible=false`。
