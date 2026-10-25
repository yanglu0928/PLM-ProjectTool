# CR-SUR-010：Review Subject 临时证明上下文

日期：2026-10-07。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09`、
Review API 与业务策略不变；本 CR 只修正 `SUR-04-A06` 接入既有 Review kernel 时发现的内部证明上下文
不兼容。

## 差异与风险

通用 Review kernel 当前只向 Subject Owner 传递已认证 `actor_id`。SurveyConclusion 在送审和批准时必须
重新证明 PROJECT_RECORD 对应 DocumentVersion、当前资格与内容指纹；既有 Evidence/Document 公共 proof
要求同一请求的 Session token，以保持当前用户、Project 角色、Document 权限与文件完整性验证在同一事务
闭环。只用 `actor_id` 直查 Evidence/Document 私表会破坏 Owner 边界；跳过 Document 重证会让撤销或文件
漂移被放行；把 Session token 写入 Review 表、Audit、日志或可打印 DTO 则会泄露 Secret。

## 选择

- 新增通用但非持久化的 `ReviewSubjectProofContext(session_token, trace_id)`，只在已完成Session/CSRF认证的
  Review submit/transition调用栈内传入 Subject Owner。
- 上下文为不可变对象，token使用`repr=False`，整个字段使用`repr=False, compare=False`；Review repository、
  Audit、receipt、响应和数据库均不得保存或返回它。
- 既有 Subject/调用者默认上下文为`None`，原行为与构造位置保持兼容；只有SRV-05 Owner强制要求有效上下文。
- SRV-05 Owner仍以已认证actor、Project授权和Review reviewer资格为权限事实；token仅供Evidence/Document
  Owner重走既有当前证明，不能替代上述权限。
- 结论创建继续只允许项目经理/实施成员取得PROJECT_RECORD证明；SRV-05复验实例显式允许全部已合格项目成员，
  使客户侧Reviewer可复验其有权评审的当前证据。默认构造策略不变，不能借此扩大创建权限。

## 迁移、回滚与验证

- 无Schema、Migration、公开API、Secret配置、依赖、客户数据或外发变化；无需数据迁移。
- 回滚可撤SRV-05注册及上下文可选参数，既有Review历史不受影响；在无安全等价证明前SRV-05送审恢复失败关闭。
- 验证覆盖token不出现在repr/Audit/receipt/数据库、既有Subject回归、SRV-05送审/批准/退回/撤回、当前
  Evidence漂移、Audit故障回滚、旧批准版SUPERSEDED及同键重放。
