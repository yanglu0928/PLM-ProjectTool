# PKG-PILOT-01-A04-P07：交接批准后调研创建入口前置核查

日期：2026-10-25；状态：`PRECHECK_PASS / SURVEY_CREATE_UI_GAP`。

|检查项|证据与结论|
|---|---|
|Phase/WBS|Phase 2 的 `CR-EXEC-002` Windows 11 Pilot 纵向链；本项仅查“已批准交接→调研定义创建”入口，不修改冻结 API/Schema。|
|输入基线|`HND-05-A05-P06` 固定非发行包 Edge/HTTPS/PG 已验交接版本批准与当前指针，合成身份不等于客户确认；分支提交 `7520de70`。|
|后端现状|`POST /api/v1/projects/{project_id}/surveys` 已由显式 Windows Survey Router 挂载，严格正文 `{name}`、CSRF/Origin、Idempotency-Key，项目 `SURVEY_CREATE` 仅 PROJECT_MANAGER/IMPLEMENTATION_MEMBER。|
|交接来源|Review 批准在同事务将固定交接版本置 APPROVED、其 CANDIDATE 问题转 CONFIRMED；Survey HANDOVER_ITEM 来源证明要求同项目 ACTIVE Analysis、当前批准版本和 CONFIRMED/RESOLVED/ACCEPTED_RISK 问题，不可直接消费 DRAFT/待确认问题。|
|前端现状|调研定义列表/详情可读取和定位固定来源，但无创建按钮/页面/`SessionClient` 调研定义 POST 桥接；用户即使完成交接批准，也不能从现有 UI 形成调研定义。|
|最小后续|`SUR-07-A01` 仅新增严格 Survey Create 私有客户端与 Session POST 桥接；`SUR-07-A02` 再建项目列表中的创建表单/入口；版本问题与固定来源编辑分独立 WBS，最后重新打固定包跑实际 Edge/HTTPS/PG。|
|验收/边界|本项是只读代码与已验包证据核对，未新跑调研写接口、未生成真人调研内容或 Pilot 包。原冻结合同不变；任何后续数据写仅用合成隔离库验收。|

风险：不能把“调研定义可创建”推定为“调研版本、访谈记录、人工确认已完成”。
业务表单只能作参考，后续问题卡片须以实际面对面调研记录及可追溯固定来源为主。
Windows Server 2025、Debian 13 正式兼容仍未由此核查证明。
