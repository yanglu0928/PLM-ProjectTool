# AUT-04-A10-P02 可选User名称PATCH

## 编码前检查

- 当前Phase/WBS：Phase2 Platform Core / AUT-04-A10-P02，Gate3未关闭。
- 输入基线：冻结64cdf09/API02 AUTH_USER_PATCH、当前0046、P01内部服务e26ce1b。
- 前置：P01实际PG通过，原Session/CSRF/Origin、强If-Match、safe User投影存在。
- 模块/实体/API：Auth/User，PATCH `/api/v1/admin/users/{user_id}`；本轮可选router，不接Windows。
- 权限：真实当前DeploymentAdmin Session-CSRF和License由原内部服务再次检查，不接受客户端actor/role。
- 验收：200 safe8字段/current trace/强ETag/no-store；严格16KiB单JSON、仅username字符串；Origin/Host/CSRF/If-Match与权限/唯一/版本/异常全矩阵；真实PG拒绝无写和Audit写后回滚。
- 风险：未知提交确认读当前GET，不盲重试；共享If-Match最大值保既有规则。无幂等Key要求，不暗加Key；默认404。License正向合成，非正式运行包。

## 决策与回滚

DEC-20260927-300：冻结未枚举完整body字段，细化为`{"username":"显示用户名"}`，与创建输入一致；服务端计算canonical。共享Auth严格JSON读取和safe投影，不扩大角色/Schema/依赖。CurrentAdmin拒绝对外404、Session过期401、CSRF/License403、版本和唯一409、缺If-Match428、畸形400、名称校验422、未知503。撤可选router和create_app参数保P01与历史；原冻结文件不改。

## 验证

HTTP_INTERNAL_PASS（Windows11隔离PG18）；非正式发行验收。

- Changed/Files：新增Auth可选`api/user_name_patch.py`、create_app显式参数；7新Contract及实际PG HTTP脚本；不默认挂载。
- Tests：1319无失败（2既有符号链接权限跳过）；真实Session-CSRF/Admin/PG PATCH200/安全8字段/强v2/trace/no-store/nosniff/noSetCookie，no-op、旧v1冲突、缺428/畸形400、Origin/Host/Session/CSRF/普通用户、禁用名称重复、未知目标、License与格式拒绝六表不变。目标DISABLED改名仍DISABLED，原first201v1重放、current GETv2均不写。
- Exceptions：实际Audit写后故障确实到达并503且六表回滚；原P01内部故障/版本/历史和双Scope空/260行发布、撤权/取消/许可/身份/锁竞争回归通过。
- Migration/API：无Migration/依赖/权限变化；新增可选冻结PATCH实现增量，原合同不追写。默认404/Windows当前未接。
- Build：开发wheel706685字节，SHA256 `328c254f1458057d434893c791e4b555d780ae148f23f31379198d6432017cf7`，非安装包，不提交wheel。
- Known Issues/Next：正向信任合成；未验提交确认恢复HTTP、浏览器、20并发、三平台、正式供给/UI/完整包；下一P03仅Windows显式write装配，Gate3不关闭。
