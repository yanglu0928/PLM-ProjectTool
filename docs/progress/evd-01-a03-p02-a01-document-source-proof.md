# EVD-01-A03-P02-A01：固定版本全文来源证明

- 日期：2026-09-26；Phase 2 Platform Core；输入：ADR-008、冻结 DM-03/API-02、EVD-01-A01/A02、Document 受权快照能力与 `DEC-20260926-138`。
- Changed：新增 Evidence 内部 `DocumentEvidenceProofService`，只通过 `PrepareDownloadService` Port 取得固定版本、已验证的私有快照，不接触或返回物理路径。`DOCUMENT` Locator 使用服务器验证的全文 SHA-256 作为内容指纹；流成功/失败后均关闭。其余八类精确定位明确拒绝，避免把全文指纹伪装为页/节/单元格证明。
- Files：`apps/backend/src/plm_assistant/modules/evidence/application/document_source_proof.py` 与测试。Migration、公开 API、新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 全文证明、无权/异常脱敏、非法与精确 Locator 不开流、错误版本关闭流、真实 `LocalFileStorage` Hash 失配拒绝并记失败 Audit 的合成测试 PASS；后端 572 项无失败（2 项既有符号链接环境跳过），开发 wheel PASS。
- Result：P02-A01 全文来源证明内部合同 PASS；测试的 DocumentReadPort 身份为合成，真实受权生产组合未装配。P02 九类精确定位、A03 候选创建、EVD 整体及 Gate 3 均未通过。不能用此结果证明 PAGE/TEXT_RANGE/SECTION/PARAGRAPH/TABLE_CELL/SHEET_RANGE/SLIDE_SHAPE/STRUCTURED_NODE 可准确跳转。
- Next：P02-A02 建立受权 Document 解析结果与八类精确定位的证明适配，依据原格式能力记录定位精度；完成后 P03 再同事务创建候选、持久幂等与 Audit。Windows Server 2025 本项未运行，Debian 13 按用户当前指令暂不验证。
