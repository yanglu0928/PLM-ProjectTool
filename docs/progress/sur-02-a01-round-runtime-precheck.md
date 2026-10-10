# SUR-02-A01：Survey Round 运行时前置核查

日期：2026-10-06。结论：`SUR_02_A01_RUNTIME_PRECHECK_PASS`。下一项：`SUR-02-A02` 两表 ORM / Migration 0107。

## 核查结果

- 冻结 SRV-03 为 PROJECT/M-PRJ `SurveyRound`，物理表固定为 `srv_rounds` 与 `srv_round_source_records`；Round 绑定不可变 SurveyVersion，四态为 PLANNED、OPEN、CLOSED、CANCELLED。
- 冻结 API 有 LIST/CREATE/GET/PATCH/OPEN/CLOSE/CANCEL 七项；创建/PATCH 允许 ProjectManager 与 ImplementationMember，状态命令仅 ProjectManager，读取为 Project member。
- 当前 Alembic head 0106 和 Survey ORM 只有 SRV-01/SRV-02 六表；代码、测试、入口和前端均无 `srv_rounds`/Round Owner/Router，因此不能把 SC 清单中的表名视为已实现。
- 当前 SurveyVersion Review Owner 已能证明 ACTIVE Survey 的当前 APPROVED Version；Evidence/Document 有固定来源证明能力，但现有 Workflow 专用 Project Evidence Service 只允许 ProjectManager且不强制 PROJECT_RECORD，不能原样冒充 Round 来源 Owner。
- CLOSE 的完整性依赖 SRV-04 Assignment/Response/Answer 当前事实。SRV-04 尚未实施，因此本阶段不得以空集合、原始 PROJECT_RECORD、模板或客户端 PASS 关闭 Round。

## 决策与拆分

按 CR-SUR-007：A02 先实现两表和数据库保护；A03 建 PROJECT_RECORD 固定来源 Port；A04 完成创建/读取；A05 完成计划修改、OPEN/CANCEL并让 CLOSE 失败关闭；SUR-03 提供真实答复与完整性 Owner后，由 A06 接通 CLOSE、HTTP/Windows/前端/浏览器。

Round 创建固定当前批准定义，后续定义升版不追写历史。现场记录由 SRV-04 在 OPEN Round 内通过 Round-owned append Port 与 FACILITATED_RECORD Response 同事务固定，不要求客户填写模板，也不把 Evidence 本身当结构化回答。

## 验证与边界

本项为编码前文档核查，无程序、Schema、Migration、API、依赖、Secret、网络或外发变化。已静态交叉核对冻结 Data Model、SC-01/02、API-01/04、CR-SUR-001、当前 Survey ORM/Migration/入口和 Evidence/Document Owner；未运行数据库或浏览器测试。Gate 3、UAT 和发行仍未通过。
