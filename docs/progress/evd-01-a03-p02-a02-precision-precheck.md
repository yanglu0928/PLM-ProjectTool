# EVD-01-A03-P02-A02：八类精确定位来源证明前置核查

- 日期：2026-09-26；结论：`PRECONDITION_BLOCKED`（仅此精确定位子项，不推翻 P02-A01 全文证明）。
- 基线：Gate 2 冻结 DM-03/API-02 要求 PAGE、TEXT_RANGE、SECTION、PARAGRAPH、TABLE_CELL、SHEET_RANGE、SLIDE_SHAPE、STRUCTURED_NODE 均可在固定 DocumentVersion 上重新解析；精度必须与源格式匹配，不能把模型摘要或全文 Hash 冒充页/段/单元格位置。
- 证据：`docs/progress/phase-2-parser-worker-precheck.md` 已明确正式 Parser/OCR Worker、ParseRecord 结果发布属于 Gate 3 后 Phase 3；目前 `apps/backend/src` 无正式 ParseRecord 结果服务。`poc/poc-05-document-ocr` 的 `ParsedDocument` 明示仅为 Phase 0 验证结构，不等于冻结的生产 DTO/权限/Job 结果。`EVD-01-A03-P02-A01` 仅能验证 DOCUMENT 全文。
- 决策：不把 PoC 解析脚本注入生产 Evidence，也不降级精确定位合同；本项保持未通过。先推进 Phase 2 允许的 DOC-04 ParseRecord 持久基础、受权读取/状态，再在 Phase 3 Parser 结果发布后实现八类真实解析证明。若提前运行正式 Parser，须按 V1.1 建立时序 Change Request 和完整跨 Gate 验证；本轮不提前扩项。
- 影响：EVD-01-A03 候选创建与 Viewer 不得开放精确定位；无代码、Migration、API 或依赖变化。`DOCUMENT` 来源证明仍为内部合同，不能外推九类。
- 恢复条件：固定版本与 ParseRecord 成功结果、来源定位结构、解析器版本/结果 Hash、各格式实际位置复验、授权及文件完整性均有生产可调用 Port，并完成失败/跨项目/漂移测试。Debian 13 按用户当前指令暂不验证。
