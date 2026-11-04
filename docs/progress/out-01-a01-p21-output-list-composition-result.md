# OUT-01-A01-P21：OutputRequest 列表接入 Windows 只读组合结果

- 日期：2026-11-04
- 结果：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-017
- Hosted run：[41846611865](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41846611865)，13/13 jobs 成功

## Changed

将冻结的 OutputRequest keyset 列表 GET 接入 Windows 显式只读组合，并配置专用当前账户 Vault HMAC key ref。默认 App 不挂载该路由；缺钥或密钥无效时显式 read 组合失败关闭，不创建、替换或复用密钥。

## Files

- apps/backend/src/plm_assistant/entrypoints/windows_output_list.py
- apps/backend/src/plm_assistant/entrypoints/windows_output_list_cursor.py
- apps/backend/src/plm_assistant/entrypoints/api.py
- apps/backend/src/plm_assistant/entrypoints/production_login.py
- 新增组合与密钥来源单元测试、PostgreSQL 18 hosted HTTP 验收脚本，并扩展父包 PG smoke 与 A17 合成密钥 fixture。

## API / Database

- API Contract、URL、query 参数、角色矩阵未改；新增的组合仍消费冻结 OUTPUT_REQUEST_LIST。
- 无 ORM、Migration 或 Schema 变化。

## Tests

- GitHub hosted run 41846611865：13/13 jobs 成功；后端 4,022 tests、wheel；前端测试/typecheck/build；父包装配及 A17/A34/A35/A50 均通过。
- PG18.6：Project Manager、Implementation Member、Customer Manager 允许；Customer Member、非成员与跨项目访问拒绝；分页、项目/page-size/session 游标绑定和篡改拒绝通过；查询前后表行计数不变；默认 App 无列表路由。
- Synthetic hosted data only；customer data=false、external API calls=0、product API started=false。
- 父包候选 20,204 项，ZIP SHA-256：ab296298508a7030262cb5494b584249fc54f0ffee6b5b209bc81eb4af24c1f1，hosted runner 使用 D: 临时路径。

## Known Issues / Limits

未验证用户 Windows 11 实机、实际服务账户 Vault 密钥供给及生产信任；不代表 Gate 3、Pilot、UAT 或正式发行通过。插件受信任清单当前为空，Output 实际生成仍受安全信任装配约束。

## Next

下一 WBS 对既有 OutputRequest 列表建立前端接入编码前检查，先核对 SessionClient、路由、权限呈现和列表分页行为。
