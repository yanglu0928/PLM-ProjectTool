# Auth Password Reset First V1 设计（未实施Schema）

来源64cdf09/API02、CR-AUT007、DEC317。当前head仍0048；本文件不代表ORM/Migration已完成。原冻结及0001～0048保留。

候选`auth_password_reset_results`15字段对应`PasswordResetResult`：result_id/user_id/actor_id/before_credential_id/credential_id/before_credential_version/credential_version/before_user_version/user_version/target_state/audit_event_id/trace_id/revoked_session_count/changed_at/accepted_at。result UUID PK，User/actor/Audit FK，前后Credential均(ID,User,version) triple FK；每User新Credential/User version及Audit唯一。accepted_at由DB statement_timestamp供给，不接受caller未来时间。

形状：UUID非零、old/newCredential不同，Credential1..bigintmax加1，User0..bigintmax加1，count0..bigintmax（停用目标无Session仍可重置），target_state仅ENABLED/DISABLED；changed/accepted有限且changed<=accepted<=本次statement time。

INSERT来源计划：锁目标User，与当前active newCredential/User version/lock version/updatedBy==actor/updatedAt==changed精确匹配，当前state==target_state。beforeCredential属同User/版本，old.changedAt<=new.changedAt<=changed、User.createdAt<=old.changedAt；新Credential必须must_change_password严格true、changedBy==actor。不更新历史或启用目标。

审计精确Auth AUT-01/目标User/DEPLOYMENT/USER actor/原trace/PASSWORD_RESET/SUCCESS、before CREDENTIAL_Vn/after CREDENTIAL_Vn+1，无originalActor/hint/project/reason/versionref，changed<=Audit.time<=accepted。全目标Session必须已撤销，count仅本次changedAt/PASSWORD_RESET实际组数，允许0，不把所有旧历史撤销算成本次。

来源层锁Admin actor，ENABLED/DEPLOYMENT_ADMIN；他人重置要求actor当前normal activeCredential，self reset新当前Credential已经受限，需历史beforeCredential normal与本人原身份专用末核，不能盲套普通末核或移除最终授权。DB约束并非Session/CSRF/License证明，完整Service须调用公共实时授权并通过专用末核。

first UPDATE/DELETE/TRUNCATE禁止；down锁表且非空拒绝，空表可撤本增量。不回填/删除历史，不强制生产降级。正式升级备份停写、实际账户与恢复演练；本轮无生产迁移。

下一P05A02实现ORM/Alembic及真实空/有数据up-down-up、旧表不变/ORM parity、正常/disabled零Session/self来源、bad flag/time/actor/trace/version/count拒绝/写后回滚/并发唯一/非空down。随后实际Repository/Scrypt来源、原子Service/Admin-License-CSRF/If-Match、最后Admin self改密可达性、HTTP/Windows与性能，均不能以本设计替代验收。
