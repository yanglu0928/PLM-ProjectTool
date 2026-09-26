# Checklist 追加记录设计 V1

日期 2026-09-26；0.1.0.dev0；CR-WFL-004；P03/0032 已实施两表并完成隔离 Schema 验证；无运行写命令/实际 Gate，证据见 P03 报告。

## 根记录

`wfl_checklist_records` 为 WFL-01 owned 追加实体，不新增业务 Aggregate Scope。record_id UUIDv7；workflow_id/project_id 复合 FK→Workflow；(workflow_id,item_key) FK→固定 Item。唯一 (record_id,workflow_id,project_id,item_key) 与 (workflow_id,item_key,after_item_version)。

字段：definition_version=1、item_key、stage_key（固定归属）；before_state PENDING/PASS/FAIL/WAIVED、result PASS/FAIL/WAIVED；before/after_item_version（+1）、before/after_workflow_version（+1）；supersedes_record_id 可空，同父/project/item 复合 self FK；actor_id User FK、trace_id、occurred_at UTC；reason/impact 可空、非空时最多 2000 字且不是纯空白；content_fingerprint 32 bytes；created_xid bigint 数据库强制 txid_current()。

实施细化：observed_stage_state 由数据库强制捕获 ACTIVE/BLOCKED，提交时必须保持相同，记录事务不得隐藏恢复 BLOCKED。FAIL 的 ReviewRound 观测白名单按冻结模型 PENDING/IN_REVIEW/APPROVED/RETURNED/WITHDRAWN；正向记录仅 APPROVED。理由/影响使用显式 Unicode 空白集合检查，避免 locale 字符类漏判中文空白。

首次必须 before_state=PENDING、before_item_version=0、supersedes 空；更正必须引用当前可信记录（不是任意同项目记录），before_item_version>0、before_state 与上一条 result 一致，不允许 PENDING 重置。新 record_id 不等于 supersedes，引用先前已存在记录，不接受循环或未来父。

Item 与 Workflow 锁版本是不同的序列；不能把 Item 版本当 HTTP If-Match。一个记录事务只修改一个 Item，Workflow 当前阶段不移动，只 Workflow 锁+1。只有当前 ACTIVE/BLOCKED 阶段允许受权记录；BLOCKED 修正不自动变 ACTIVE，也不自动推进。

## 依据引用

`wfl_checklist_record_refs` 保存 record/workflow/project/item 复合 FK；ref_kind EVIDENCE/REVIEW_ROUND/APPROVED_EXCEPTION、ref_id、ref_scope/ref_project_id、observed_state、observed_lock_version、content_fingerprint、verified_at、proof_schema_version。unique(record,kind,id)。EVIDENCE 生成 evidence_id 连接真实 Evidence 身份 FK；Review/例外缺目标表须明确记录，未来通过 Owner 证明并独立补关系，不假造 FK。

PASS/WAIVED 至少一固定 Evidence 与 Owner 解析出的正式 ReviewRound；Evidence ELIGIBLE，Review APPROVED。WAIVED 必须有批准例外和非空 reason/impact；PASS/FAIL 不用例外替代判断。FAIL 可为空 refs；若保留依据，仍必须受权、同项目/允许 GLOBAL Evidence、类型/版本/指纹真实，不因结果 FAIL 放宽项目隔离。FAIL 观测状态允许记录未通过/待判定事实，具体白名单及 Owner 映射在 Schema/应用任务分别验证，未知类型失败关闭。

根与 children 不可修改，子项只能在根创建事务追加。Evidence 在写事务共享锁并比对观测事实，提交时重验；后续目标合法状态变化不能篡改已提交记录。UTC 时间/Hash 是观测数据，不是可信签名或批准凭证。

## 原子性与授权

服务先认证/License，再写事务重新认证 CSRF/PM、锁 Project/当前成员/部门/Workflow/Item，强 If-Match 为 Workflow lock。根插入前核对当前 Item 状态/版本与上一条可信记录，及 Workflow 当前阶段/版本；提交时核对 Item result/after 与 Workflow after/阶段不变。Audit/收据/记录/引用/两个当前投影一起提交，异常全回滚。

无写服务时 SQL 结构只证明形状与事务一致，不能证明真实客户批准。未来 Gate evaluator 必须读取与当前 item.lock_version 一致的完整不可变记录、受权重新证明其依据，并把固定记录引用保存在 GateItem；当前只有旧 0031 结构，补关联前不开放 Gate 写路由。

## 验收矩阵

领域：固定十二 Item/阶段归属、首次和更正、三结果、锁序列/UUID/UTC、不可变、WAIVED 依据、未知/重复引用/自循环/可变集合拒绝。

Schema：空库 up/down/re-up、0031 旧初态与合成已判断状态升级原样不变、不自动造历史；完整初次记录、更正链与 refs，跨 Project/Item/Scope/旧父/未来/重复版本/错误状态拒绝，半套提交/并发/追加封口/非空 down 拒绝，ORM parity。

应用：真实 PM/Session/CSRF/License/归档/撤权、Owner Scope/版本/批准/制品证明、每次独立重验、新 PASS 不能复用撤销依据、历史/Audit/幂等一致、失败结果不能推进；HTTP 与 Windows 组合、覆盖率/性能另验。

领域与 Schema 的隔离合成矩阵已在 P02/P03 执行，实际应用/Owner/HTTP/覆盖率/性能仍待；既有 0031 证据不替代本次记录链验收。Server 2025 未运行，Debian 13 暂不验证，完整 Workflow/Gate/可用程序包未完成。
