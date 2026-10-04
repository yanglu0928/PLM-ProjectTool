# 中文扫描页与原生文本页定位复验

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P04-A01`。结论：`WINDOWS11_SYNTHETIC_MIXED_PDF_PASS`，仅覆盖一份本机生成的双页 PDF。

验证脚本用本机中文字体生成“项目范围已确认”图像，并放入临时 PDF 第二页；第一页是原生英文文本。独立打开文件确认第一页确有可提取文字，第二页没有可提取文字。现有离线 PP-OCRv5 模型从本地候选字节复制到临时 ASCII 路径运行，不下载模型、不读取客户文件。正式 Parser 将第一页输出为 `PDF_TEXT_LINE`，第二页输出为 `OCR_LINE`；中文识别结果与合成字样一致，两个节点的页码分别为 1、2，第二页归一化 PAGE bbox 与嵌图区域相交。两节点均通过直接 Locator 与固定 ParseRecordId/NodeId 的 STRUCTURED_NODE Evidence 证明。

脚本真实退出 0，临时模型与文档自动清理。本项只新增验证脚本和记录；生产代码、公开 API、ORM/Schema、权限、依赖、发行包及升级路径均未变化。本项未重跑全后端与 wheel；原 Parser/OCR 定向回归属此前 WBS 结果，不重复计数。

已知边界：仅一行中文和两页合成布局，不证明复杂合同、低质扫描、旋转、多栏、真实客户文档的 OCR 质量或坐标精度。模型副本不等于正式发行信任材料；Windows Server 2025、Debian 13、Gate 3 和整体程序包仍未验收。冻结的 SECTION Locator 还没有 Parser 来源节点，本项不能关闭该缺口。
