# SUR-07-A03：调研定义创建 Windows 11 非发行包验收

日期：2026-10-25；状态：`SYNTHETIC_PACKAGED_EDGE_PG_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A03`；仅证明调研定义 UI Create 在固定包内真实运行，不添加版本问题或冻结 API 变更。|
|输入基线|`SUR-07-A01/A02` 已通过前端全量2022/typecheck/build，干净源提交 `10c8b72cc64a194704be2f00c8b738958a64cd46` 已推送。|
|包源|后端自 `98df564e` 至当前无文件差异，可复用 P06 已验证 wheel SHA `b2053a4a4b3e1648293514cbfd59f73786b227e3a2abf64ce4d11a7e99d10d4e`；固定 parent SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。候选只替换当前前端 dist，并绑定打包时的干净 HEAD。|
|验收|独立清洁解包/逐件哈希；复用包内合成项目→交接批准链后，在真实 Edge/HTTPS/隔离 PG 中从项目调研列表创建定义，验证唯一 Survey/Audit/收据、同号重放、只读角色/跨项目/License 拒绝、临时进程/Vault/布局清理。|
|安全|仅合成账户、TLS 与 License；不上传 ZIP/Secret/客户资料，不把调研定义当访谈事实，`release_eligible=false`、`legal_clearance=false`。|
|回滚/已知缺口|无 Schema/API/License 改动；失败保留候选与证据，先修复后重建/重测。正式公钥、服务账户/CA/法律、离线升级、调研版本/实际记录、UAT/Gate/正式多平台仍未验。|

前置核查通过。第一次打包器正确拒绝未提交的前置记录（源码非干净 HEAD）；
记录提交 `794ac7916c54133b53d4962e324005279ad90ba8` 后，重建固定非发行候选。
直接运行解包脚本因默认系统 Temp 与指定隔离 Temp 不一致而被拒，首次改用
`runpy` 后缺工具模块搜索路径再被拒；修正执行环境后才开始独立解包，未在上述
拒绝轮次安装服务或写数据库。这些是验收环境/调用偏差，不是产品功能 PASS。

## 独立验收结论

- 固定候选 ZIP SHA-256：`fea9bb417d40839cbd2191d429bfc92ab008442edbddb571b3479af394bad194`，
  源提交 `794ac7916c54133b53d4962e324005279ad90ba8`；22,196 件载荷及 3 件
  清单独立清洁解包逐件哈希退出 0，`release_eligible=false`、`legal_clearance=false`。
  ignored ZIP 与独立解包目录留本机复核，不上传 Git。
- 新包内 Windows 11 Edge/HTTPS/Caddy/Python 3.13/隔离 PostgreSQL 18 完整前序
  项目→固定文档/Evidence/能力→交接 DRAFT→校验/送审→客户合成 Reviewer 批准
  复跑通过；已批准交接两张问题卡片在 PG 中均为 `CONFIRMED`。
- 受权合成实施成员从真实调研列表 UI 提交定义；浏览器同操作号重放返回原
  SurveyId。PG 验证仅一条 ACTIVE 定义、零调研版本、唯一 `SURVEY_CREATED`
  成功 Audit、唯一 `V1_SURVEY_CREATE` 完成收据。匿名、错误项目、客户只读角色
  创建拒绝；合成 EXPIRED 投影后创建 403 且定义数量不变。
- 全流程退出码 0，候选字节未修改，临时 PostgreSQL/Caddy/Python/Edge、Vault
  和安装布局清理；独立解包目录保留。P06 Review 验收钩子只供本轮在批准后、
  合成失效前插入调研测试，原 P06 验证流程仍在本轮通过。

本轮不证明实际访谈记录、调研版本问题与固定来源或真人确认。下一 WBS
`SUR-07-A04` 核查并打通“已批准交接问题→调研定义首个 DRAFT 问题版本”的
真实用户入口。正式信任/法律/离线安装升级/UAT/Gate 3～7/Pilot/三平台 Release
继续 NOT_READY。
