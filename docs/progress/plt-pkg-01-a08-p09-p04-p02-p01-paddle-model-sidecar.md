# PLT-PKG-01-A08-P09-P04-P02-P01：Paddle 模型离线旁包

## 编码前检查

- 当前 Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P04-P02-P01；仅解决锁定 Paddle det/rec 模型的离线归档和新 ASCII 路径重装。
- 输入基线/前置：`audit_paddle_model_revisions.py` 锁定的两组 revision、10 个 Git/LFS 对象及运行时指纹；CR-PAR-005 已记录中文模型路径失败。现有候选仍非发行包。
- 模块/实体/API/权限：只新增模型旁包工具与测试；不改 Parser 生产配置、实体、API、数据库、License 或服务账户权限。
- 验收：源对象与缓存 revision 一致；归档逐件 Hash、路径安全、固定指纹和非发行标志通过；全新 ASCII 解包 10/10 Hash 一致，嵌入式 Python/Paddle 对合成 PNG 与混合 PDF 执行真实 OCR。
- 风险/回滚：归档未锁定目标 ACL 或部署账户，不能接入发行；旧候选不覆盖。移除新工具和经核对的忽略旁包即可回退，保留原来源审计历史。

## Windows 11 实测

- 本机 Git 忽略的 `artifacts/package-prep/windows11/NOT-FOR-RELEASE-paddle-models-v5.zip`，18,691,648 字节，SHA-256 `944ec7f8f7b7815ec9c35443afe980ad5207a5ed653c55cde573fd5e20c06c69`。
- 旁包清单明确 `release_eligible=false`；det/rec 两个固定 revision、10 个模型/README 文件和运行时指纹 `511580fe3e72fe1759ce18ac05d5454eee88865303603631be644a4978889cf4` 通过归档回读。验证器拒绝重名、越界/非 ASCII/符号链接路径、不匹配来源对象、变化的源文件及冒充发行的清单。
- 在全新 `C:\Users\17231\AppData\Local\Temp\plm-paddle-sidecar-reinstall-20261001` 解包，11 个归档条目清单与实际数量一致，10/10 模型文件 SHA-256 匹配。嵌入式 Python3.13.15 在该 ASCII 路径用 PaddleOCR 完成合成 PNG 1 行、混合 PDF 原生文本 1 行/OCR 1 行，exit 0。
- 定向单元测试 4/4 PASS（含已有来源审计），无客户资料外发。该路径继承当前用户权限，不代表 `C:\PLMTool` 目标 ACL、服务账户读/普通用户不可写或 Server 2025 验收。

## 待续

下一子项核对目标安装目录、管理员和独立服务账户的只读 ACL/Hash 门禁及失败回退；之后才可做完整 Windows 11 OCR 离线重装。Tesseract 官方包无效 Authenticode、61 DLL/4 JAR 精确来源与许可、真实独立 OCR 质量、AGPL/产品许可和其他目标机仍阻断发行，`release_eligible=false`。
