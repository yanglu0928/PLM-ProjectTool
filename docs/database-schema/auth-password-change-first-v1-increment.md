# CR-AUT-007 改密首次结果Schema增量

2026-09-27 / 0.1.0.dev0 / 0048_SCHEMA_VERIFIED_APPLICATION_PENDING。
原冻结64cdf09及0001～0047保留；新增Migration20260927_0048（down0047），无生产迁移。

auth_password_change_results：result_id PK、user_id、before_credential_id/credential_id、before_credential_version/credential_version、before_user_version/user_version、audit_event_id、trace_id、revoked_session_count、changed_at、accepted_at（DB statement_timestamp默认）。私有坐标不得直接公开；响应仅新credential_version。

前后Credential三列FK精确同User/版本，版本各+1、UUID非零/凭据ID不同、count>0、有限有序时间；User新凭据版本/资源版本/Audit分别唯一。INSERT source精确当前enabled User及自己updatedBy、新active Credential必须normal/changedBy自己、前后凭据时间与User更新、self PASSWORD_CHANGED Audit前后CREDENTIAL_Vn状态、trace与时间；全部Session已撤销，同updatedAt/PASSWORD_CHANGED实际撤销计数一致。它不是密码匹配或前置事务/权限证明。

追加结果不可UPDATE/DELETE/TRUNCATE；非空down拒绝并保历史/原head。空库及有数据升降往返十二旧表保持、ORM parity和拒绝/回滚实际验证见P03A02progress。未来升级必须备份及停写；有历史回滚撤入口保数据库，不回写旧密码或复活Session。没有本轮新Key、依赖或公开API。
