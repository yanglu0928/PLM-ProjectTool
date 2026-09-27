# AUTH_USER_PATCH实现增量（原冻结64cdf09保留）

版本：0.1.0.dev0；日期2026-09-27；Trace：AUT-04-A10-P01 / DEC-20260927-299。

当前只完成内部服务，HTTP与Windows写模式尚未挂载。冻结PATCH由当前DeploymentAdmin、Session、License、CSRF、If-Match与Audit控制；本项没有新角色、Schema或依赖，不改冻结合同。

名称使用原Auth NFC/trim/casefold规则，更新display与canonical，唯一约束包含DISABLED身份。用户UUID、状态、角色、密码及版本、活动Credential指针、创建元数据、Session不变。名称改变后登录改用新名称；旧名不继续指向用户，也没有永久别名保留机制。首次User创建结果及原Key重放永远保留创建时View，不把当前GET当首次响应。

内部expected_version必须真实非负bigint，先比较版本再判no-op；fresh no-op不提交、不加版本、不Audit；实际改名版本+1、更新人/时间与固定USER_NAME_CHANGED Audit同事务。固定Audit不包含用户名正文。未知来源、DB/提交确认故障静态不可用；不凭错误判定已提交或未提交，客户端后续GET核对版本，禁止盲重试。

验证：Windows11隔离PG18内部竞争/唯一/历史/异常回滚通过；HTTP输入名、If-Match解析、返回ETag/错误映射留P02验证。未宣称生产License/浏览器/性能/三平台/完整包通过。
