# CR-SUR-005：Survey 原子送审可选元数据处理

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09`、Schema 0106 与 Review 历史保留，不追写原冻结内容。

## 来源与冲突

冻结 `SURVEY_VERSION_SUBMIT_REVIEW` 请求保留 `due_at` 与 `submission_note` 两个可选槽位，但当前通用 PROJECT Review Schema、`SubmittedProjectReviewRef` 和持久幂等回执均不保存这两项。若 Router 接受非空值后丢弃，将向调用方虚报数据已被保存；若在本 WBS 临时扩充 Review Schema，则会跨越 Review Owner、查询投影、迁移和多个业务 Subject 的兼容边界。

## 方案比较与选择

- 方案 A：接受并静默丢弃非空值。会造成不可追溯的数据损失，拒绝。
- 方案 B：本项同步扩充通用 Review Schema。超出单一 WBS，且需要所有 Subject、迁移、读取与升级路径共同评估，拒绝。
- 方案 C（选择）：保留冻结四字段请求形状，但 V1 明确要求 `due_at=null`、`submission_note=null`；非空返回 422，不写入也不送审。未来确需持久化时，另建跨 Review Schema 的 Change Request，并保持当前 null 请求兼容。

## 影响、迁移与回滚

不修改 URL、字段名、Schema/Migration、ORM、依赖、角色、Secret、网络或外发范围。ProjectManager 才能调用；Review 创建、首轮启动、SurveyVersion 进入 `IN_REVIEW`、Audit 和幂等回执仍在一个数据库事务中完成。

应用回滚方式是不注入 Survey 送审 Router；合法 Survey/Review/Audit 历史不得删除。未来扩展两个字段时必须新增存储、读取投影、迁移/降级保护和兼容测试，不能改变既有 null 请求含义。

## 验证计划与结果

- 合同：精确四字段、固定 `SURVEY_ALL_V1`、非空可选元数据 422、Origin/Session/CSRF/License/幂等与安全错误映射。
- 原子性：Audit 失败时 Review/Round/SurveyVersion/receipt 全回滚；成功时创建 Review 并直接启动首轮。
- 重放：同 Key 返回首次 Review/Round，仍重验当前 Project 与 Survey Subject 访问，不重建 Review。
- 当前事实：来源漂移拒绝终态批准，恢复后批准；批准后仍能重放首次送审结果；后续新版本可独立送审和撤回。
- 结果：定向19项通过；Windows 11/PostgreSQL 18.6 真实链输出 `SUR_01_A05_A05_SUBMIT_REVIEW_PASS`；后端全量2838项通过、3项跳过；wheel 1049 entries，SHA-256 `170083bd760238bff4948b3a9bed3613d523d18dfd991030de4c4aed4917a3b7`。
