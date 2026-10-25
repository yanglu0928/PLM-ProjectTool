# SUR-07-A04：交接问题到调研首版来源的前置核查

日期：2026-10-25；状态：`PRECHECK_PASS / SOURCE_DISCOVERY_GAP_RECORDED`。

|编码前检查|证据与结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A04`；只核查交接已批准问题能否由用户安全选为首个 SurveyVersion 来源，先登记 CR，不改冻结代码。|
|输入|`SUR-07-A03` 固定非发行包 SHA `fea9bb41…4bad194` 已验交接两问题 CONFIRMED、调研定义 UI 创建；真人客户/访谈仍未确认。|
|写合同|冻结 `SURVEY_VERSION_CREATE` 要求完整问题快照、至少一题和一目标部门、强 Survey If-Match、幂等 Key；`HANDOVER_ITEM` 源必须含 `handover_item_row_id`、固定 VersionId、AnalysisId。|
|客观差距|交接 GET 只输出稳定 `analysis_item_id`；`HandoverAnalysisItemRow` 创建时另生不同的 `analysis_item_row_id`。在既有交接/调研公开 API 与前端中未找到首版所需固定行 ID 的受权发现入口；Survey 内部只读证明 Port 不可直接交给浏览器。|
|不能采用|不能由浏览器猜 ID、直查私表、把 MANUAL 当交接固定引用，或静默改变冻结交接 GET DTO；这会破坏来源资格/Trace 与旧严格客户端。|
|已记录调整|`docs/changes/CR-SUR-013-approved-handover-source-discovery.md`：新增独立只读来源候选操作，当前项目/角色/批准指针/问题状态过滤，旧 POST/GET 保持；选取后写事务再重证。|
|范围/验证|本项只读静态核对，无 HTTP/PG 版本创建、无 Schema/Migration/Secret/外发。后续 `SUR-07-A05` 先实现 Owner/API/Windows 并测隔离/撤权/分页，再做客户端/页面/固定包。|

业务表单只能作为参考；实际面对面调研记录与人工问题卡片需后续维护，不能从
交接批准或模板自动推出客户答复。Pilot、Gate 3～7、正式三平台发行仍 NOT_READY。
