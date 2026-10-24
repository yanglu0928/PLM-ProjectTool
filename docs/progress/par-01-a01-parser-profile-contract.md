# PAR-01-A01 固定版本 Parser 输入与策略合同

- 日期/结果：2026-09-30；Phase 2 依赖前置；`BACKEND_CONTRACT_PASS`。编码前检查：Gate 2 冻结 Document/ParseRecord、ADR-007、POC-05 六格式技术验证；EVD-01 精确定位仍缺生产解析结果，先按 `CR-PAR-001` 记录实施时序偏差。决策 `DEC-20260930-497`。
- Changed/Files：新增 `modules/parser/application/profile_selection.py`、包入口和单元测试。输入严格绑定固定 DocumentVersion UUID、32 字节 SHA-256、0～100 MB 大小及检测 MIME；支持 PDF、DOCX、PPTX、XLSX、CSV、纯文本和 PNG/JPEG/TIFF，策略带版本号。PDF 仅选择“文本优先，必要时 OCR”的未来执行策略；图片选择 OCR 必需，PaddleOCR 排首位。未知 MIME 与畸形/改写输入失败关闭；不传文件路径或正文。
- Tests：定向 3 项 PASS；Python 3.13.15 后端全量 1569 项 PASS（2 项既有符号链接环境跳过）；隔离构建 wheel PASS，确认新模块 3 个文件进入 wheel。首轮机器默认 Python 3.14 未设置项目导入且缺依赖，全量 569 项/239 错误，不计产品回归；切正确 3.13 虚拟环境后全量通过。非隔离 wheel 构建因该虚拟环境未安装 `setuptools` 失败，隔离构建重跑通过。
- 兼容/升级/回滚：不改生产 API、ORM/Migration、权限、Job 队列或第三方依赖，兼容冻结 `/api/v1`/DB0049；无升级动作。可撤独立 Parser 合同回滚，不触碰业务历史。
- Known Issues/Next：策略选择不是文件受权、Hash 复验、格式内容解析、OCR 质量或 Worker 执行证据；没有创建 SUCCEEDED ParseRecord、ResultRef 或精确 Evidence Locator。下一项应建立受权固定版本 Parser 输入 Port/真实文件复验，再逐格式解析、结果发布和定位验证；Gate 3、Server 2025/Debian、正式信任及可用程序包仍未通过。
