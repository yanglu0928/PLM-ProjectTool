# AUT-04-A09-P04：可选User创建HTTP

2026-09-27 / OPTIONAL_HTTP_PASS；当前Windows写装配未完成。

编码前检查：Phase2 / AUT-04-A09-P04；输入冻结API02 AUTH_USER_CREATE/CR-AUT-005/0046；前置P03真实原子与确认丢失验证已同步eef52f1。仅Auth API/create_app可选router和测试，无Schema/依赖/权限变化。部署管理员/有效Session-CSRF/License/I/A与201 UserView不变；默认和现Windows组合不自动开POST。

实施前细化：body仅显示`username`与write-only `password`字符串，canonical/actor/role由服务端决定；不增加管理员提升。16KiB流式JSON上限，严格单Content-Type/UTF8/重复key/NaN拒绝，不接query；继承已有Origin/Host/Cookie/CSRF/Key校验，预验Session后调用P03再实际授权。初始ENABLED/NONE/credential1/lock1安全八字段UserView、ETag/Location/no-store/nosniff；重放仅首次结果、Envelope trace是本轮。

错误映射：普通Admin外用户404、失效会话401/CSRF403、License403、同Key冲突409、用户名冲突映射冻结CONFLICT_DUPLICATE409、语义422/格式400、源/KDF/事务故障503静态；无密码/hash/参数/私有source/traceback。HTTP+Service各自尽力擦buffer，不承诺删除框架/Python所有副本。撤optionalrouter回滚保历史；无生产迁移。

验收：Contract success/default404/严格输入/来源headers/安全错误和清理；真实PG HTTP Session-CSRF/Admin/幂等与初始真实登录凭据/历史停用重放/六表拒绝无写、原P03与读取回归。完整浏览器/Windows装配/正式供给/性能/最终包另验。

## 执行证据

六新Contract：default404/201安全字段与当前trace、Origin/Host/Cookie/CSRF/Key前置、duplicateJSON/extra role/NaN/types/UTF8/NUL/超长/错CT/query/重复安全headers、静态错误与非首次metadata503、所有已分配password buffer擦除。全后端1304无失败，2既有Windows符号链接权限场景跳过。

`validation/aut-04-a09-p04-user-create-http/verify.py`真实PG18/P03实际原子/真实Session-CSRF/Admin+Scrypt：201/Location/首ETag/no-store/nosniff/无Set-Cookie/密码不回显，原Key重放data同但当前trace不同；密码/用户名同Key冲突与canonical新Key冲突；初始新密码签发真实有效Session（不是登录HTTP），非Admin404。恶意headers/strict body/未知和被停用Session401/角色撤权404/License403均六表全行无写。目标停用改名GET v2而原201重放仍v1，不复活；实际Audit写后HTTP故障到达并全回滚。原P03并发/九故障/commit确认丢失与双Scope实际文件发布回归附此validator再次通过。

开发wheel702043 bytes，SHA256 `236d7878f5accb665a01a8f851272573474bfd046a9008233ea6be8242102597`；仅忽略本地产物，不是发行包。

Changed/Files：Auth User create router/create_app opt-in、六Contract/实际validator、API增量、本文/DEC297/CR/STATUS/CHANGELOG。Migration/API：head0046不变，新增已冻结POST的可选实现、无Breaking/依赖/权限变。Result：可选HTTP内部PASS。Known Issues：Windows当前未挂、正向License合成/框架秘密副本/真实浏览器/20并发/正式供给/三平台/完整管理/Gate/最终包未完。Next：AUT-04-A09-P05仅Windows显式write装配与实际回归。
