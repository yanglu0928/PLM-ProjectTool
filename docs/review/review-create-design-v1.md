# Review identity 创建设计 V1

2026-09-26；RVW-01-A06；来源 AF-02、DM-02 Review、API-02 REVIEW_CREATE/ResourceVersionRef、CR-RVW-001、0034 与 A04/A05；内部命令设计，不改冻结 HTTP 字段或表。

## 身份创建与送审分离

创建只建立 PROJECT Review 逻辑身份，DRAFT/lock_version=0/active_round_id=NULL，不创建 Round、Assignment、Subject Snapshot/锁或正式业务版本，不宣布送审/批准。输入 subject type/id/version 为内部固定引用，Actor 从真实 Session/CSRF；Project 从受控路径上下文；只允许当前 ACTIVE Project 的 ProjectManager。DeploymentAdmin 无旁路，非 PM 拒绝，GLOBAL 留独立策略。

Owner 在同事务核验当前 Actor 对逻辑主题的管理权、固定版本真实归属与创建资格，保持身份/版本授权事实锁，返回绑定 actor/project/type/id/version 的窄结构及服务器 policy_code。未知 Owner/错误绑定/跨 Scope/缺版本/无资格/不可用拒绝；客户端不能用 owner_module、任意策略或 UUID 替代。Review 不读写业务 Owner 内部表。

CREATE 的 version 是当次 Owner 前置校验输入，不是已经锁定的送审 Snapshot；Review 根仍按冻结 DM 只绑定逻辑主题。未来 START_ROUND 必须重新核验当次固定版本、政策兼容、真实确认人资格、来源/内容快照和真实 Owner 身份锁，不复用创建时观测作为批准或版本锁。输入 version 参与命令指纹；创建审计绑定新 Review，不能把业务 Version 冒充 Review 根的版本。只有 START 的实际固定 Snapshot 才持久保存送审 Version/来源，不保存正文或生成假 Evidence。

## 幂等与事务

复用既有通用 receipt（0034 已包含的 0015），operation=`V1_REVIEW_CREATE`，结果 ref_type=`V1_REVIEW`/status 201，Scope actor/project/key 摘要，命令指纹只含规范固定引用。新建 Review、Audit REVIEW_CREATED、完成收据必须同事务提交，Audit/Owner/receipt 故障全部回滚。不得新增仅为方便的 Schema 列或把 Key/客户正文写入收据。

内部创建返回不可变 CreatedReviewRef（review_id、project、逻辑 subject、immutable policy、created_by/created_at），不返回会变化的当前 Review state/etag。该引用可由根不可变创建字段稳定重建，因此重放不会把后来轮次的新状态假充首次响应，不需要新增响应正文持久层。公开 HTTP 的冻结 Review identity 投影另行设计验收，不直接序列化内部 Ref，也不以本任务标 HTTP PASS。

所有重放仍重新验证当前 Session/CSRF/License/PM 与主题访问权，不能借旧 Key 绕过撤权；完成收据重放不重复要求原版本仍为待送审状态，也不重建 Round/写 Audit。当前设计保持 ACTIVE Project 要求，归档后的 CREATE（包括重试）拒绝，不引入归档写旁路。新 Key 是独立创建请求；0034 没有逻辑主题 Review 唯一约束，不静默加入该业务规则或将所有新 Key 强制合并；送审时唯一 ACTIVE Subject 身份锁继续保护并行轮次。

锁序：Auth/Project 当前事实 → 同 Key 收据 → 创建 Owner 身份/版本 → 新 Review insert（新根无需锁已有 Review）；重放取旧根时为 Project→receipt→Review→Owner。Owner CREATE/读取授权应有明确分离；后续 START/DECIDE/撤回统一 Project→Review→Owner→Round。真实跨模块锁验收待真实 Owner，不将合成 Port 当生产锁。

## RVW-01-A07 验收计划

内部 PM 创建命令、窄 Owner Port、Review owned create/replay Repository、Project REVIEW_CREATE 策略、Audit/通用收据；无新 Schema/公开 API/依赖/角色。单位验资格/身份绑定/UTC/版本/政策码、未知 Owner、异常脱敏、原子提交和重放；隔离 PostgreSQL 使用真实 Session/CSRF/Project/Review/Audit/receipt，Owner/License 明确合成：四角色/跨项目/Admin/归档拒绝，同 Key 并发一次创建/一次 Audit，异 payload 冲突，故障全回滚，后续根状态变化不改首次 CreatedReviewRef。

无真实 Owner 时默认拒绝，不装配 HTTP；实际资格/版本锁/客户审批和公开链仍客观未完成。先按 WBS 完成内部可验模块，不跨 Phase 构造虚假业务主题，不删除原业务 Scope。

## 升级与回滚

需已安装 0034；本设计不增加迁移或修改原冻结版本。停用内部创建服务即可回滚，历史/收据/Audit 不删除；非空 Review owned 历史仍遵循 0034 down 拒绝。升级前备份、生产不可恢复操作不在持续授权内。
