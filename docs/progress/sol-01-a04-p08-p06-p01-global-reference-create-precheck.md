# SOL-01-A04-P08-P06-P01：GLOBAL Reference Create 前置核查

日期：2026-10-09；结果：`GLOBAL_CREATE_PRECHECK_PASS`，仅冻结合同/Owner/组合证据静态对账，不代表 GLOBAL Create HTTP、真实人工确认或正式发行通过。

编码前检查：Phase 2；输入 Gate 2 冻结 API-04、CR-SOL-006/007/009/010、ReferenceSolution 初版 Schema/Owner、P05 多来源 Edge/PG 合成验收。前置确认账本/撤回与来源证明、单/多来源界面机制在 Windows 11 合成环境已验；Gate 3 未通过。本项只确定创建入口可否安全进入实现，不改生产代码、Schema、API 或权限。

对账：冻结 `SOL_REFERENCE_CREATE` 已展开 `/api/v1/global/reference-solutions`，请求仍为 `name`、有序 DocumentVersion/Evidence ID、来源项目分类、脱敏分类、适用性六字段；不接受客户端自报确认 ID。现有 `ReferenceCreateService` 已支持 GLOBAL：要求当前 DeploymentAdmin Session/CSRF/License，Source Qualification 在同一写事务重算当前文件与 Evidence 集合指纹，按该指纹读取最新未撤回且未过期的人工确认，并校验分类/适用性；Repository 持久记录该 ConfirmationId、初始版本/来源/Audit/幂等收据。PROJECT HTTP/Windows 组合已验，但现有公开路由 `_response` 明确限定 PROJECT，生产组合未挂 GLOBAL Create。P05 Edge 脚本勾选的确认仅是合成技术证据，不是正式资料脱敏事实。

决定与顺序：P06-P02 增可注入 GLOBAL Create HTTP，严格复用冻结六字段和现有 Owner，不新增客户端确认 ID；默认/只读应用保持 404。P06-P03 在一次性 PG/文件/真实 Session/ASGI 验证无确认、错集合/分类、已撤回/过期、跨权限、重放、审计回滚与成功绑定真实本轮合成确认 ID；不得用脚本结果宣称客户实际确认。P06-P04 仅在 Windows 显式写模式和完整依赖时装配，缺正式信任源失败关闭。P06-P05 再接前端创建入口，并在创建前重显来源、当前确认状态及结果非正式批准的边界；真实用户与正式 License/目标账户分别列发行 Gate。当前不能因为单/多来源合成 Edge PASS 就直接放开 GLOBAL Create。

偏差/风险/迁移/回滚：现有冻结 CREATE 合同足以承载，不需 Change Request 或 Schema/依赖变化；新增仅兼容公开路径与组合。风险为引用脚本确认、过期/撤回后旧确认复活、历史首次回执冒充现时资格、跨管理员/失权重放；Owner 的现时证明与每次创建重新校验必须保持。回滚关闭新路由/UI，已创建的 Reference/版本/Trace/Audit/确认历史不得删除。正式 License/服务账户、Server 2025、20 并发、Gate 3/UAT/发行和真人资料核查未验；Debian 13 依用户指令跳过。

TraceLink：冻结 API-04/CR-SOL-006/007 → CR-SOL-009/010 → P05-P03 Edge/PG → 本 P06-P01 → P06-P02～P05。
