# AUTH_USER_PATCH实现增量（原冻结64cdf09保留）

版本：0.1.0.dev0；日期2026-09-27；Trace：AUT-04-A10-P01 / DEC-20260927-299。

当前已完成内部服务及可选HTTP router，仅Windows显式write挂载；readonly GET-only返回405，普通默认与login-only仍404。冻结PATCH由当前DeploymentAdmin、Session、License、CSRF、If-Match与Audit控制；本项没有新角色、Schema或依赖，不改冻结合同。

名称使用原Auth NFC/trim/casefold规则，更新display与canonical，唯一约束包含DISABLED身份。用户UUID、状态、角色、密码及版本、活动Credential指针、创建元数据、Session不变。名称改变后登录改用新名称；旧名不继续指向用户，也没有永久别名保留机制。首次User创建结果及原Key重放永远保留创建时View，不把当前GET当首次响应。

内部expected_version必须真实非负bigint，先比较版本再判no-op；fresh no-op不提交、不加版本、不Audit；实际改名版本+1、更新人/时间与固定USER_NAME_CHANGED Audit同事务。固定Audit不包含用户名正文。未知来源、DB/提交确认故障静态不可用；不凭错误判定已提交或未提交，客户端后续GET核对版本，禁止盲重试。

HTTP输入仅`{"username":"显示用户名"}`，16KiB单JSON，拒绝重复字段、NaN、错误UTF8与额外role/actor/canonical。复用单强If-Match；无需Idempotency-Key。成功200安全8字段/current trace/ETag/no-store/nosniff；当前Admin拒绝404、失效Session401、CSRF或License403、版本与重复409、缺版本428、畸形400、名称校验422、未知503。

验证：Windows11隔离PG18内部、可选HTTP及实际writeFactory版本/唯一/历史/权限/严格输入/异常回滚通过，1319后端无失败（2既有跳过）；真登录旧名401/新名200同UUID、原Session有效；readonly隔离/构造失败关闭/实际缺正式信任拒绝通过。未宣称生产License/浏览器/性能/三平台/完整包通过。
