# PLT-PKG-01-A08-P09-P02-P02：ASCII 模型新目录 OCR 实测

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P02-P02；Tesseract 安装包获取受阻，转不依赖它的 Paddle 模型路径验证。
- 输入基线与前置：CR-PAR-005 方案 A、P02-P01 固定上游模型 revision、现有 Windows11 嵌入式 Python3.13 后端候选。
- 模块/实体/API/权限：仅本机 OCR 安装前置实测；无解析器、实体、API、权限、Migration 改动。
- 验收：从已锁定本地来源新复制 det/rec 模型至全 ASCII 绝对路径，10 个文件逐项 SHA-256 对比，运行现有合成 PNG/混合 PDF OCR 脚本；记录目标目录 ACL 与剩余差距。
- 风险/回滚：临时目录继承用户可写 ACL，不是正式安装位置；测试不写业务数据，原模型和候选包不变。

## Windows 11 实测

测试目录 `C:\Users\17231\AppData\Local\Temp\plm-ocr-ascii-check-20261001` 为本轮新建 ASCII 路径，包含 det/rec 各 4 个运行文件及 README；源/目标 10/10 文件 SHA-256 一致。使用 `artifacts/package-prep/windows11/embedded-backend-20261001-003655-949d77fb/runtime/python.exe`（Python 3.13.15，PaddleOCR 3.7.0/PaddlePaddle 3.3.1）运行 `apps/backend/tests/integration/verify_parser_ocr_synthetic.py`，退出码 0：合成 PNG OCR 1 行、PDF 原生文本 1 行及扫描页 OCR 1 行均符合断言。无需外部模型下载或客户文件。

该目录 ACL 继承 `YangLu\17231` FullControl、`CodexSandboxUsers` Modify 等用户写权限，不能用作发行目标目录。正式方案仍按 CR-PAR-005 A：模型置于受控 ASCII 路径，运行账户只读，管理员/SYSTEM 可更新；安装器须先核对固定来源 Hash 再原子部署，重启后验证同一 OCR 链。此处未验管理员安装、服务账户 ACL、Windows Server 2025、Tesseract/Ghostscript 集成或完全断网。

Tesseract 安装包的 UB Mannheim 发布页已确认，但本机到发布主机 TCP 443 超时，安装包 Hash/签名仍缺。`release_eligible=false`，CR-PAR-005 保持 OPEN。下一项优先补安装器安全部署/回滚设计与测试；正式系统组件来源及三平台验收继续排队。
