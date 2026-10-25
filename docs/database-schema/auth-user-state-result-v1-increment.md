# Auth User状态首次结果Schema增量

版本0.1.0.dev0；日期2026-09-27；Trace CR-AUT006 / DEC-20260927-303 / AUT04A11P02。原冻结64cdf09和0001～0046保留；新增0047，未迁移生产。

`plm.auth_user_state_results`为不可变首次响应历史，不是User当前状态或权限源。PK result_id；FK user_id/actor_id→auth_users、audit_event_id→aud_events；unique(user_id,lock_version)与audit_event_id；保存safe8UserView及private operation/expected_version/revoked_session_count/trace/acceptedAt。无hash、密码、Sessiontoken、canonical或密钥。

约束要求非零UUID、名称长度、原两种role、credential>0、lock_version=expected+1、ENABLE→ENABLED且count0或DISABLE→DISABLED、非负撤销数、有限ordered时间。INSERT trigger先锁target，精确匹配当前User元数据、activeCredential与有效版本、updatedBy、固定USER_ENABLED/USER_DISABLED Audit及USER/DEPLOYMENT/AuthAUT01目标/actor/trace/逆before和after、无reason/Hint/originalActor及时间。acceptedAt<=本次statement_timestamp，避免伪造未来受理时间。

DISABLE额外要求目标无任何未撤销Session，count匹配同一User updatedAt和USER_DISABLED的真实撤销事件组；包含超时但未撤销Session。Session写、原因和timestamp必须由未来命令与User更新同事务实现，表本身不替代这些写操作或证明原状态转换。ENABLE不复活已撤销Session。此快照不能替代当前Admin/Session-CSRF/License、最后Admin计数、合法自停用末核或receipt指纹。

UPDATE/DELETE/TRUNCATE禁止。升级0047不回填旧状态；下行先ACCESS EXCLUSIVE，非空拒绝丢弃历史。正式升级须人工备份/维护停写；回滚撤入口保历史，不能为降级删除snapshot或Audit。需要旧代码运行时按兼容性和停写措施评估，不承诺自动回滚。

Windows11隔离PG18空/有数据升降往返、十一旧表保留、ORM一致、源拒绝/2Session含expired计数、插入故障回滚、历史不可改与非空down拒绝已验证。实际状态命令/幂等/自停用/权限/HTTP/生产/性能/三平台/发行仍待，不将TEST_ONLY schema凭据说成认证成功。
