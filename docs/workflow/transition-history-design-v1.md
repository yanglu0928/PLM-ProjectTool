# WFL-02 相邻迁移追加历史设计 V1

日期 2026-09-26；0.1.0.dev0；CR-WFL-003；状态 DESIGN_ONLY，0031 尚未创建。

## 数据结构

统一 UUIDv7、timestamptz(6)/UTC、bigint、text+named CHECK；NO ACTION FK，普通 UPDATE/DELETE/TRUNCATE 拒绝，追加事务中的父子插入由提交时 deferred 校验完整性。保存少量理由/影响（最多 2000 字符）和引用，不保存正文或密钥。

|表|身份、归属和唯一性|事实列|
|---|---|---|
|wfl_stage_transitions|stage_transition_id；workflow_id/project_id 复合 FK；unique(id,workflow,project)；unique(workflow,after_lock_version)|definition_version=1；definition_fingerprint 固定 V1；transition_type=FORWARD；from/to 固定相邻 pair；before_lock_version>=0、after=before+1；actor_id User FK；reason 非空；occurred_at、trace_id；gate_fingerprint 32 bytes；created_xid bigint 由数据库强制设置|
|wfl_transition_gate_items|gate_item_id；transition/workflow/project 复合 FK；unique(transition,item_key)；unique(id,workflow,project)|item_key/required/result；required 必须等于固定定义（V1 均 true）；result PASS/WAIVED；对应 Evidence/Review 策略引用；WAIVED actor User FK、reason/impact 必填；PASS 时豁免列为空|
|wfl_transition_gate_refs|gate_ref_id；gate_item/workflow/project 复合 FK；unique(gate_item,ref_kind,ref_id)|ref_kind EVIDENCE/REVIEW_ROUND/APPROVED_EXCEPTION；ref_id；ref_scope GLOBAL/PROJECT、ref_project_id；observed_state、observed_lock_version>=0；content_fingerprint 32 bytes；verified_at；proof_schema_version=1|

所有 row 身份 UUID 非零，引用不允许字符串 latest/current。Gate fingerprint 由未来受控服务按版本化 canonical 格式生成；第一项 Schema 只校验长度，不谎称数据库会验证所有业务内容或签名。

Evidence 可为 GLOBAL 标准引用或同项目 PROJECT；ReviewRound/ApprovedException 必须 PROJECT 且 project_id 与 Workflow 相同。refs 增加只在 ref_kind=EVIDENCE 时取 ref_id、其他类型为空的 generated evidence_id，连接现有 Evidence FK（身份），不能将所有类型 UUID 错连 Evidence。受权 Owner Port 负责固定内容/DocumentVersion/Scope/当前 eligibility=ELIGIBLE 与事实锁；插入结构触发器可以核对当前 Evidence 的 Scope、版本、指纹和状态，但不得由 Workflow Repository 承担跨模块查询授权。历史观测后允许目标状态正常变化，不在未来 unrelated 提交时把旧 snapshot 强制等同当前状态。Review/例外目标尚未实施，先存固定类型引用和观测字段，不能猜造 FK或批准。

ReviewRound 的观测状态必须 APPROVED。APPROVED_EXCEPTION 必须 APPROVED，批准人与权限须由未来例外 Owner 证明；一个例外 ID 不是批准证明。Evidence 的 fingerprint 是已有固定内容摘要，Review/例外的 fingerprint 后续 Owner 根据固定决定提供，Workflow 不自行计算客户事实。

## 提交完整性

1. BEFORE INSERT 锁 Workflow 父行，防并发历史冲突；根行记录实际 actor/定义/阶段/版本，成功记录不承载失败尝试。
2. 每个 FORWARD 根恰有来源阶段两项 Gate，固定 key/required/策略，不能借用目标阶段或重复遗漏。
3. 每项至少一条 EVIDENCE、一条 REVIEW_ROUND；PASS 不含 APPROVED_EXCEPTION、豁免列全空；WAIVED 有完整批准例外引用和 actor/reason/impact，不改写失败质量指标。
4. refs 的类型/Scope/项目/状态/版本/摘要长度校验；Evidence FK保护身份。Review/例外没有目标表时，绝不据 SQL 插入成功宣称引用真实。
5. root/children 追加只读、父对象不可漂移、NO ACTION、不允许保留 root 缺子项或保留孤儿。提交后不能补写子项改变快照；root.created_xid 由 BEFORE INSERT 强制写 txid_current()，客户端不能指定其他事务标识；BEFORE INSERT 所有子项须要求根的 created_xid 等于当前完整事务标识。具体 SQL 经独立实现评审与真实 DB 测试，不允许靠时间戳或可伪造会话变量判断。普通使用者不能禁用触发器；数据库超管权限不在应用威胁边界。

## 应用层开放前置（本 Schema 不实现）

Workflow/当前 Stage/Checklist/Project/成员事实锁；重新校验 Session、PM、CSRF、License、非归档和强 If-Match；来源由服务器确定；解析已有 Checklist 追加记录的完整依据，再通过 Evidence/Review/业务 Owner 同事务 Port 复验全部 required。请求 refs 仅为选择依据，不能替代事实。

只有所有证明成立，才能一次事务保存当前 Stage 完成/目标 Stage ACTIVE/Workflow 指针与锁版本、不可变 Transition/Gate refs、Audit 与幂等收据。失败只记录安全拒绝 Audit，不留下成功 Transition 或半套更新。即使 Domain snapshot 构造成功，也必须做上述证明。事务提交前不能释放被引用的可变 eligibility/批准事实锁。

首次 START 的历史/进入条件、Checklist 追加记录、最终 PLAN 完成 API、BLOCKED 恢复需后续独立任务；当前 FORWARD Shape/三表不得替代这些功能。原 Scope 保留。Owner 前置缺失时转 Review 等独立 Platform Core 任务，不跨 Phase 实现业务事实。

## 数据库验收矩阵（全部待执行）

- ORM 与真实 SQL 反射 parity；空库全量 up/down/re-up；0030 有 Project/NOT_STARTED/合成 ACTIVE 升级，原状态与 Audit 均不变，无自动历史。
- 合法相邻根+完整 Gate/ref 一次事务提交；全部 36 阶段 pair，仅五组合法；缺根/跨项目/父漂移/非法策略/缺项/多项/重复 refs/无依据豁免拒绝。
- root 无子项、item 无 refs 和错误 Scope/观测状态提交失败；失败事务不留历史。
- UPDATE/DELETE/TRUNCATE 禁止；提交后新增 child 拒绝；并发同 after_lock_version 收敛或明确冲突，不产生双成功。
- 非空 down 拒绝并保留三表；空 down/re-up 可用；当前 Workflow 读/初始化、所有后端测试与开发 wheel 回归。
- 实际 Owner 授权、Gate 与生产信任源另验；Server 2025 未运行、Debian 13 暂不验证，不声称性能或发行通过。
