# AUT-04-A11-P04 可选User状态HTTP

## 编码前检查

当前Phase：Phase2，Gate3未通过。当前WBS：AUT-04-A11-P04。
输入基线：64cdf09 API01/API02、CR-AUT006。前置任务：P03真实原子链9e9f9c3已通过。
涉及模块/实体：Auth User/Session/statefirst；只复用已验Application。
涉及API：AUTH_USER_ENABLE/DISABLE冻结POST，显式可选router，默认关闭；本轮不接Windows。
涉及权限：当前Admin/License/Session-CSRF/Origin、Key和强If-Match；当前认证先于历史恢复。
验收标准：安全首UserView/ETag/当前trace，严格空body/query/header；静态错误；真实PG拒绝无写/历史重放/回滚/自停用Cookie、新认证重放不得误删新Cookie。
风险：自停用首响应后认证失效；无法依据历史first判断当前Session是否已撤销，需当前真实Session再次读取。提交后读取不可用返回503，原Key恢复，不盲重试新Key。License原独立UOW及20并发/三平台/正式信任未验。

DEC-20260927-305：冻结命令无输入字段，要求空body，不接受{}或客户端actor。对内部CONFLICT_STATE映射冻结AUTH_USER_DISABLED409；lastAdmin具体原因不公开。成功只safe8字段，私有撤销count/actor/source不公开。自行DISABLE按请求前真实principal.user_id判断，再读取当前Session：实际失效才清Cookie，新认证历史重放有效则不清；未知读取失败503保留原Key恢复。无Migration/依赖，回滚撤可选router保历史。

## 验证结果

2026-09-27 / 0.1.0.dev0 / OPTIONAL_HTTP_VERIFIED_WINDOWS_PENDING。

- 新router由create_app显式可选参数安装，默认404；两冻结operation ID及路径不变，状态冲突码落实冻结AUTH_USER_DISABLED409。安全8字段/强ETag/no-store/nosniff/当前trace，不公开first私有坐标。
- 8项新HTTP contract tests：两命令成功、格式/重复Header/Origin-CSRF/Key/If-Match/空body/UUID/Session失败、静态错误、坏结果绑定、自停用Cookie及未知末读拒绝。全后端1344 tests无失败，2既有Windows符号链接权限跳过。
- 实际PG18/Scrypt/ASGI验证：两状态转换、同Key首响应、目标后来启用仍重放历史、旧Session不复活/新Session有效；版本/Key/当前非Admin/CSRF/Origin/License拒绝七表不变；实际Audit插入后故障全回滚。
- 自停用成功删除Secure/HttpOnly/SameSite=lax/Path=/ Cookie，原Session再次请求401；重新启用后的新认证重放返回原first且不删Cookie/不写七表。实际提交后Session复读故障返回503，但数据库v5及唯一first已提交；重新启用后以新认证+原Key恢复v5，当前新Session继续有效。
- 新增末读验收首轮因验证SQL误用DTO字段account_state而失败；核对ORM后改为真实列state，生产逻辑未改、断言未放宽，再跑通过。原双Scope文件发布回归通过。
- 最新开发wheel719338 bytes，SHA256 `d9925d478b0378342774c3a681fda97269ba5b2a8c760e4a4a59f554bf8e9a56`；不是可安装发行包，不提交wheel/测试数据。

兼容0047，无Migration/依赖/生产迁移/角色变化；回滚撤可选router保历史。正向License合成，Admin提升为显式TEST_ONLY夹具。Windows尚未接线，正式信任/性能/浏览器UI/三平台/包/Gate3未通过。下一AUT-04-A11-P05仅Windows显式write装配及实际组合验证。
