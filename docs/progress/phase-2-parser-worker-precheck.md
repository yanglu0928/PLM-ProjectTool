# Phase 2 → Phase 3 Parser Worker 前置核查

日期：2026-09-26；状态：Phase 3 正式解析执行器暂不进入编码。

《PLM项目实施辅助工具软件开发实施方案 V2.1》第 Phase 2 Platform Core 将 Document/Evidence/Workflow/Review/Trace 列为任务，Phase 3 AI/RAG Platform 才列 Parser/OCR/Chunk/RAG 与统一 AI。当前 Gate 3 尚未通过。`CR-DOC-006` 为 Phase 2 上传提交所需，已提前建立 PostgreSQL Job/Outbox、领取/投递和 Parse 入队 Port，但不授权把真正 Parser/OCR Worker、ParseRecord 结果发布与 AI/RAG 链误记为 Phase 2 已完成。现有 `apps/backend/src/plm_assistant/modules/document` 未发现正式 Parser/ParseRecord 服务；PoC 解析脚本不等于正式受权业务模块。

后续 Phase 3 输入：不可变 DocumentVersion/FileObject 完整性证明、正式 Document 下载与授权、Job fencing/Outbox 消费、Parser Profile/Version、ParseRecord 历史、页/段/表格定位、主辅 OCR 规则、失败重试/取消与结果原子发布。若 Phase 2 必须提前运行真正 Parser，则先建时序 Change Request、风险/迁移/回滚与跨 Gate 验证；当前不这样扩项。Phase 2 独立可推进项是受权 Document 列表/版本读取及流式下载、Evidence/Trace/Review/Workflow 等。
