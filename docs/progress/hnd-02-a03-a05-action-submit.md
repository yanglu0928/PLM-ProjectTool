# HND-02-A03-A05：Action SUBMIT Owner

日期：2026-10-05。结论：`HND_02_A03_A05_ACTION_SUBMIT_PASS`。下一项：`HND-02-A03-A06` Action VERIFY Owner。

## 实施结果

- 当前assigned owner或ImplementationMember可在强ETag匹配时把Action从IN_PROGRESS推进到SUBMITTED；ProjectManager仅凭角色不能代提交，除非同时为当前负责人。
- 每次提交至少固定一个当前项目ACTIVE Document的AVAILABLE DocumentVersion和一条定位于本次响应文档集合的PROJECT/ELIGIBLE Evidence；响应文档和Evidence按请求顺序保存为不可变引用。
- Root、`IN_PROGRESS -> SUBMITTED`事件、`submitted_at`、响应/Evidence引用、Audit和actor作用域持久幂等收据在同一事务提交；同Key重放返回首次固定引用且重验当前权限。
- 无Migration、公开HTTP、依赖、配置或外发变化；复用Schema0100。SUBMITTED不等于VERIFIED或CLOSED。

## 验证

- Win11/PostgreSQL 18.6真实临时库验证通过：owner/ImplementationMember、非owner ProjectManager、强ETag、重复状态、缺失Document、无关Evidence、并发幂等/冲突、Audit失败整笔回滚恢复及License拒绝。
- 定向17项，后端2637项通过/3跳过；wheel解包17项通过，SHA-256 `8973d6e6134fd044d112d64da9364248679d9a6aa6d20ba393231e420c1084dd`。
- 验证偏差：首轮实施成员夹具使用了不足16字符的幂等键，按输入边界正确返回`VALIDATION_FAILED`；该轮未作为通过证据，修正夹具后以全新临时库完整重跑通过，产品实现未调整。
- 无公开HTTP、网络或外发；VERIFY/CLOSE-CANCEL及后续Review/HTTP/UI仍待，Gate 3继续BLOCKED。
