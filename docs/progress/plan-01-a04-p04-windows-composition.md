# PLAN-01-A04-P04：Windows 11 Plan 当前身份 HTTP/PG 装配

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A04_P04_WINDOWS_COMPOSITION_PASS`（仅合成信任功能验收）。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A04-P04`|
|输入基线|冻结 PLAN_CREATE/GET/LIST、Plan A03真实PG Owner、A04-P01～P03 默认关闭合同、Windows当前账户 Vault 模式|
|前置任务|Plan 0169 与真实创建/读授权通过，专用 signed cursor HTTP 合同通过；正式公钥/License 信任仍无，允许以合成信任验 Windows 功能但不声明生产 PASS|
|涉及模块/实体|Windows Plan 专用 cursor key provider、Plan 路由组合、现有 Windows 显式平台应用；不改 Plan/Version Schema|
|涉及 API|冻结 `POST/GET /api/v1/projects/{project_id}/plans` 与 `GET /api/v1/projects/{project_id}/plans/{plan_id}`；默认应用不挂载|
|涉及权限|CREATE 仅写模式且现时 Project 授权；GET/LIST 两显式模式、Session/License/Project 每次重验；缺服务账户专用 key 时启动失败关闭|
|验收|独立 key 丢失/备份恢复；两平台模式路由/缺钥失败关闭；Win11真实HTTP/PG CREATE→GET→LIST/同Key重放/隔离/撤权/License/默认404；定向/全量/wheel|
|风险|测试 key 冒充正式账户、组合根意外打开写权限、缺钥回退、CREATE 与 LIST 同路径路由顺序、合成 License 被误称生产信任|

执行仅使用一次性合成信任及可弃 PostgreSQL，正式服务账户密钥/公钥和离线安装仍必须独立验收。若无法取得客观环境证据，功能保持待验并转独立 WBS。

## Changed / Files / Migration / API

- Changed：新增固定 `project-plan-list-cursor-v1` 的当前运行账户 Vault 只读来源，缺失/错长/异常均拒绝显式平台启动，不生成、不复用其他密钥；新增 Plan Windows 读/写 Owner 组合。`--platform` 仅 GET/LIST，`--platform-write` 再开放 CREATE，登录专用/普通默认应用仍404。
- Files：`windows_plan.py`、`windows_plan_cursor.py`、`production_login.py`、对应 key/组合合同测试和 `validation/plan-01-a04-p04-windows-composition/verify.py`。
- Migration：无，数据库继续使用0169。API：仅显式装配既有冻结 PLAN_CREATE/GET/LIST，无路径/字段/角色/License 变更。
- Rollback：移除可选装配即可关闭网络入口，既有 Plan/收据/Audit 历史保留；升级前目标服务账户必须独立供给并离线备份32字节游标密钥，密钥变化使旧分页游标失效。

## Tests / Result

- Windows 11 真实 Credential Manager 一次性测试引用：生成加密备份、删除 Vault 凭据、确认丢失、从备份恢复并用旧签名游标继续解码；测试凭据最后删除，不作为正式密钥。两显式平台模式缺 key 时启动拒绝且数据库 Runtime 被释放，错误不泄露原始内容。
- Windows 11 可弃 PostgreSQL 18.6 + 真实 Session/Project/ASGI：普通应用 GET/POST 404；只读模式 GET/LIST 有效而 POST 404；写模式 CREATE 201、同 Key 重放唯一、冲突409、GET当前身份、LIST 五页无重复、跨项目/撤权/匿名/恶意 Origin/CSRF/License 拒绝；SQL最终5行 Plan、3条创建 Audit。License 为合成信任，不等于正式签发或目标账户验收。
- 定向 `test_windows_plan_cursor.py` 与 `test_production_login.py` 46项/28子例；后端全量3809通过/3跳过/5991子例，新增路由断言又定向回归44项/25子例。开发 wheel 1442项，包含新 Windows 组合和 key 模块，SHA-256 `512cdbbb80be48f4d2630699edf1fc577668607d8ca799cccf078968fea884ae`；不是 Pilot/Release 包。

## Known Issues / Next

正式服务账户的专用密钥、正式 License 公钥/可信时间/HTTPS、离线安装和升级仍未验；Win11 合成验收不代表 Windows Server 2025 或 Debian 13。Plan 前端、版本/WBS/输出链和列表大数据量索引/性能仍待；Gate3/Pilot/Release 均未通过。

Next：`PLAN-01-A04-P05` Windows 11 Plan 当前身份前端项目入口及真实浏览器验收前置。
