# AUT-04-A12-P04-A03 可选改密HTTP

编码前检查：Phase2/Gate3未通过；基线64cdf09/API02/CR-AUT007，前置d309270内部原子服务已验；Auth本人Session/CSRF/current_password/new_password/Idempotency-Key，无License/Admin/If-Match。只增可选router，默认关闭，无Schema/依赖变化。

验收：实际PG/Scrypt/ASGI普通及受限改密、安全唯一credential_version响应、旧Session失效清Cookie、新有效认证历史恢复不误清新Cookie，来源/重复JSON/大小/类型/查询/坏密码/CSRF/Key拒绝无写，实际提交后确认故障503再新登录同Key恢复。未知输出拒绝无秘密。

DEC-20260927-315：复用可信Origin/Host与有界严格JSON，不接受客户端User坐标。首次成功后核当前Session，明确失效才delete Cookie；历史重放保有效新Cookie。末读未知503不猜提交失败，登录后原Key恢复。回滚撤可选router保历史，HTTP接Windows组合另任务；不以可选ASGI证明正式服务/完整包。

## 结果

新增可选router/create_app参数和增量合同，默认404。1368 tests无失败（2既有跳过），3新unit覆盖unknown output/密码擦除/形状及原始JSON surrogate安全拒绝。首轮surrogate测试由httpx编码预先报错，未到达服务端；改原始JSON转义字节后422通过，未放宽生产检查。

实际PG/Scrypt/ASGI验证来源/CSRF/Key/错原密码/客户端UserId/类型/空密码/重复JSON/NaN/16385bytes/query/Content-Type拒绝八表不变；License合成guard禁用仍可正常改密（冻结合同无L）。成功200单credential_version/trace/no-store/清安全Cookie、旧401，新有效Session原Key历史重放不清Cookie、差异409。真实提交后末读注错503且无秘密/不误清，新登录原Key恢复。TEST_ONLY受限Credential来源经实际POST转normal且新密码实际登录。不是已实现reset证明。

原双Scope发布回归通过；开发wheel735734 bytes，SHA256 `b03263329e42ec9f873050ab6ccfd02e82990890e3b9b5679768ab3af59bb559`，非安装包。无Migration/依赖/生产升级，兼容0048，撤router保历史。可选HTTP内部PASS，实际浏览器/Windows组合/性能/三平台/正式供给/包/Gate待。下一P04A04仅Windows显式写模式装配及actualFactory验证。
