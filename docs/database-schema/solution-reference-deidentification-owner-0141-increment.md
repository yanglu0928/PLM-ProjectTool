# SOL-01-A04-P02-P03-P02：人工脱敏确认 INSERT Owner 0141

日期：2026-10-08；依据 CR-SOL-006。0141 仅替换 0140 确认表的行触发器：允许 INSERT，UPDATE/DELETE 继续拒绝，TRUNCATE 仍拒绝。ORM 结构不变，既有确认历史不迁移。应用层唯一受控写路径为 Solution 内部确认命令，先验证当前管理员 Session/CSRF/License，再同一事务重新证明 Document/Evidence 固定来源、固定人工声明、30 天内有效期、幂等收据、记录和 Audit。数据库 INSERT 能力本身不能替代应用层授权，也不是公开 API。

隔离 PG18.6 验证：0140 闭锁及前序 Schema 回归、0141 升级/空表降级重升、Alembic drift、INSERT/不可变历史/非空拒降、合成命令的单记录单 Audit 幂等与 Audit 失败回滚通过。后端全量 `3290 passed, 3 skipped, 4820 subtests passed`。PG 命令夹具使用合成 Admin/来源 Proof，不能宣称真实登录+文件端到端或人工核查已完成。0141 降至 0140 仅限确认表为空；有记录时拒降并保留历史。撤回将由独立受控任务实现，不能直接改库。
