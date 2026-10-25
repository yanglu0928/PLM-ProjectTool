# EVD-05-A02：GLOBAL Evidence 创建包内验收

日期：2026-10-24；状态：`SYNTHETIC_POSITIVE_EDGE_PG_PASS / NEGATIVE_MATRIX_PENDING / PILOT_NOT_READY`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `EVD-05-A02`；仅验证新 Evidence 候选创建在固定 Windows 11 非发行包内的真实 Edge/PG 行为，不在本项代替人工资格确认。|
|输入基线|`CR-EXEC-002`、冻结 `/api/v1`；`EVD-05-A01` 前端定向8、全量1912/typecheck/build PASS；源码提交 `af08577faa7c593b70df8c8451fc713fe9562ed5`。|
|前置|固定父包 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；后端自上一候选未变，复用 wheel SHA `efb548e82ee304a91d319dea79207861446b5250f51ed4e74f323164c5f19e62`；pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。|
|模块/实体/API|仅新增验收夹具；Document/DocumentVersion、CapabilityBaseline 前置，GLOBAL Evidence CANDIDATE、`EVIDENCE_CREATED` Audit、`V1_EVIDENCE_CREATE` 收据；不改产品 Schema/API。|
|权限/安全|一次性合成 DeploymentAdmin、PG18/Caddy HTTPS/Edge/License；无客户正文、真实公钥或私钥进入候选。|
|验收|包体逐件哈希与清洁解包，同 SHA；Edge 选择固定 GLOBAL 标准能力版本创建整文档 CANDIDATE，反读列表；PG 校验同源、指纹、单候选/Audit/收据及无资格批准；临时 Vault、进程、布局清理。普通成员/匿名/失效许可/错源负例须独立补证，不能由正向通过推定。|
|风险|候选法律放行与正式信任均为 false；这不是安装/UAT/Pilot/正式 Release，整文档 Locator 不是精确页段。|

候选 SHA `5b8e38f4f8e5440c74e7e0ecace43e435b4464ab5a8ae37e4010ecfdce4f1327`，654,863,398 字节、22,191 载荷，`release_eligible=false`、`legal_clearance=false`；独立清洁解包已通过。候选 ZIP 保持本机忽略路径，不上传 GitHub。

## 首轮运行记录

包内 Workflow HTTPS/合成 License 与上一段 GLOBAL 文档/基线 Edge/PG 前置链通过；新增 Evidence 浏览器脚本在登录后使用整页导航，导致前端内存 Session 投影丢失，创建页按权限正确关闭，等待表单超时并退出 1。未提交 Evidence POST，不能据此宣称新入口通过或产品创建失败。首轮隔离服务与布局已清理；夹具改为应用内路由导航后，将使用同一候选 SHA 复验，保留本失败记录。

## 同候选正向复验

改为应用内导航并等待来源元数据加载后，同一候选 SHA 重新通过两份 22,194 件隔离布局、包内 PG18/API/Caddy、合成 License/Workflow 前置与 GLOBAL 文档/基线来源 Edge/PG 链。新增真实 Edge 登录管理员、从合成 GLOBAL 标准能力固定版本创建整文档 Evidence 候选、返回列表核对；6 个相关 API 响应无非 2xx/加载失败/运行异常，标记 `EVD_05_A02_PACKAGED_EDGE_POSITIVE_PASS`。

隔离 PG 核对恰一条 GLOBAL Evidence，`locator_payload={"locator_type":"DOCUMENT"}`、指纹等于同一 DocumentVersion 内容 SHA，资格仍 `CANDIDATE` 且无决定原因，`EVIDENCE_CREATED` Audit 与 `V1_EVIDENCE_CREATE` 幂等收据各一。包内验收器退出 0；`fixed_candidate_unmodified=true`，原候选 SHA 不变；48 个合成 Vault 目标、临时进程/目录均清理。首轮失败保留在上节，不伪装为一次通过。

此结果仅关闭 `EVD-05-A02-P01` 正向合成切片，`EVD-05-A02-P02` 仍须独立验证匿名/普通成员/失效许可/错误来源在包内 HTTP/PG 下失败关闭且零业务副作用。人工资格确认、CapabilityVersion/Review、真实信任/法律/安装/UAT/Gate/Pilot/三平台发行均未由本轮通过。
