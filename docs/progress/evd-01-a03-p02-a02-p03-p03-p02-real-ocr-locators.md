# 扫描 PDF 与图片的离线 OCR 来源位置复验

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P03-P02`。结论：`WINDOWS11_SYNTHETIC_REAL_OCR_PASS`，只代表本机合成输入与当前离线模型。

验证脚本从已有非发行候选模型目录将检测、识别模型复制到临时 ASCII 路径，不下载或外发任何源文件；用本机字体新建带 `PROJECT SCOPE APPROVED` 的 PNG，再把它作为扫描图像嵌入 PDF。正式 `OfflinePaddleOcr` 对两个实际落盘文件运行；两者分别生成 `IMAGE_OCR`、`PDF_TEXT_THEN_OCR` 的 `OCR_LINE` 节点，实际识别文本均为预期字符串。PNG 的归一化 `PAGE` bbox 与原绘字区域相交；PDF 页无原生可提取文字，其 bbox 与嵌图区域相交。两份结果的每个节点均经直接 Locator 和固定 ParseRecordId/NodeId 的 STRUCTURED_NODE Evidence 证明。模型指纹与结果一致。

验证脚本退出 0，原 OCR 解析定向单元测试 4/4，临时模型/图像/PDF 自动清理。本项仅新增验证与文档，无生产代码、API、ORM/Schema、权限、第三方依赖或发行包变更；无迁移与升级动作。前项后端全量测试及 wheel 结果不在本项重计。

已知边界：bbox 相交是最小位置一致性验证，并非逐字或真实文档坐标精度评估；只覆盖一行英文、单页 PNG 和扫描 PDF。本机模型来自现有候选而非正式发行信任材料。中文、多页/旋转/低质扫描、OCR 质量指标、客户材料、正式授权组合、Server 2025/Debian 与 Gate 3 均未验收。
