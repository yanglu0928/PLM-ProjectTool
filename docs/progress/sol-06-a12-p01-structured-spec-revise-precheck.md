# SOL-06-A12-P01：结构化专项修订前置核查

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVISE_PRECHECK_PASS`，不代表修订程序或 HTTP 已实现。TraceLink：冻结 `SOL_SPEC_REVISE` → DM-05 不可变版本 → 0164 完整 DRAFT → A09 CREATE → A10/A11 详情与历史 → 本项。
- 编码前检查：冻结路径为 `POST /api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:revise`，角色为 ProjectManager/ImplementationMember，结果为 replacement DRAFT 201。现有 Repository 已支持同 series 的 `version_no + 1` 与 `supersedes_version_ref`，但公开 CREATE 只允许首版，且当前无独立修订权限、命令、收据、Audit 或 HTTP。
- 决策：修订正文沿用 CREATE 的六字段完整快照，不让客户端提交 `spec_series_id`、版本号或前驱。路径 `spec_id` 是期望替代的固定版本；服务端在同一事务内锁定该行与系列最新行，注入 series/前驱并要求路径版本仍为最新。`spec_type` 必须与系列一致，所有需求/章节/证据重新证明，附件在 OutputArtifact Owner 缺失期间继续拒绝。
- 状态边界：允许基于当前最新 `DRAFT`、`RETURNED` 或 `APPROVED` 产生新 DRAFT；`IN_REVIEW` 必须先结束/撤回评审，`RESTRICTED` 不可绕过限制，`SUPERSEDED` 或非最新路径返回版本冲突。创建新版本不改写前驱状态；已批准前驱在替代版获批前仍保留原正式事实。
- 幂等/授权/Audit：新增独立项目操作 `SOL_STRUCTURED_SPEC_REVISE`、收据操作 `V1_SOL_STRUCTURED_SPEC_REVISE` 和 Audit 动作 `SOL_STRUCTURED_SPEC_REVISED`，不复用 CREATE。请求指纹绑定 ProjectId、路径 spec_id 和完整正文；每次含重放均重检 Session/CSRF、License 和当前项目角色。同号重放先读取持久收据并核对结果 `supersedes_version_ref == spec_id`，即使系列后来再次修订仍返回原 201；首次请求才执行“当前最新”检查和来源重证。
- 事务/并发：Repository 增加受锁的 revision-base 读取，ProjectId + spec_id 防枚举；首次修订继续使用 series advisory lock 和最新行锁，陈旧前驱、并发双修订、跨项目、类型漂移、来源失效或损坏历史均失败关闭。不得以列表顺序或前端判断代替服务端当前性。
- 兼容性/升级/回滚：无 Schema、冻结路径/请求字段、License 权益或依赖变更；新增内部策略和可选 Router 可逐项撤回，已写不可变版本/Audit/收据必须保留。Windows Server 2025/Debian 13 未实测。
- 验证：静态交叉核对冻结 API-04、DM-05、0164、当前 CREATE Service/Repository、详情/列表 Repository、项目权限和 Reference revise 幂等先例；本项无运行程序变更，未执行新业务测试。
- 实施顺序：P02 受锁 revision-base/Repository；P03 独立修订 Service/策略/收据/Audit；P04 默认关闭 HTTP；P05 Windows/真实PG；P06 前端；P07 Edge。专项 VALIDATE/SUBMIT REVIEW 在 A13/A14 独立处理。
- Next：`SOL-06-A12-P02` 实现同事务 revision-base 和替代版本 Repository，先验证 v1→v2、陈旧/跨项目/状态/类型/并发及回滚，不开放 HTTP。
