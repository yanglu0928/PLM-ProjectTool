# SUR-03-A05：Assignment SUBMIT 当前回答完整性 Owner

日期：2026-10-06。结论：`SUR_03_A05_ASSIGNMENT_SUBMIT_PASS`。下一项：`SUR-03-A06` VALIDATE/RETURN、退回更正重提与状态矩阵。

## 实现

- 新增内部SUBMIT Owner：锁定OPEN Round、IN_PROGRESS Assignment、固定Version问题、当前无后继Response/Answer/Evidence；按当前assignee、部门成员或ImplementationMember动态授权，完成Session/CSRF/License、Audit、持久幂等后原子进入SUBMITTED。
- 逐题按顺序只以更早且当前活动的问题答案求值有界ConditionRule；非活动问题的残留历史答复不参与后续条件。活动题执行required、六类型、固定option及TEXT/NUMBER/DATE/MULTIPLE_CHOICE/ATTACHMENT ValidationRule。
- 所有当前Evidence在同一事务经Evidence/Document Owner重新证明DocumentVersion、lock和fingerprint；TEMPLATE、撤销、漂移或facilitated source未进入Answer Evidence均失败关闭。附件值必须精确等于Evidence顺序，并执行数量与扩展名规则。
- 为执行已冻结的`allowed_extensions`，内部Document固定来源事实增加`original_display_name`，Evidence证明只向内部Owner透传；不改变公开DTO、Schema或文件内容边界。提交回执是首次命令结果而非当前状态读模型，后续调用方仍须GET刷新。

## 验证

- Windows 11/PostgreSQL 18.6：条件题跳过、必答/规则、EvidenceRequired、撤销漂移拒绝、PM越权/CSRF/License拒绝、同Key双线程收敛、Audit故障整笔回滚与同Key恢复、精确状态/Audit/receipt计数及Alembic drift均通过。
- 后端全量`2896 passed / 3 skipped`、`4193`子断言；wheel`1081`项，SHA-256 `2b59bc885c3aed47a379f1c046ee176316be4f9c992d7bd198a309b310940b37`。wheel不是最终交付安装包。
- 验收夹具首次尝试修改不可变问题定义、第二次遗漏Evidence更新审计字段，均被数据库守卫正确拒绝；夹具改为仅在建模阶段受控装载定义并按真实Evidence状态命令投影后，从全新临时库重跑通过，产品守卫未放宽。

## 兼容与回滚

无Migration、公开API、依赖、Secret或外发变化；内部固定来源事实新增可空字段，既有调用保持兼容，生产Document Owner提供真实名称。停止后续组合可阻止新提交，已提交Assignment/Audit/receipt与答复历史保留。A06状态Owner、A07 Round完整性、CLOSE/HTTP/UI/浏览器、Gate3/UAT及发行仍待。
