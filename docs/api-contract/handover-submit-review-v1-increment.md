# Handover Version 原子送审 HTTP V1 增量

日期：2026-10-05。实现基线：冻结 API-01/API-02/API-04、DM-05、CR-HND-006；不增加或改名 Operation。

## Operation

`HND_VERSION_SUBMIT_REVIEW` 使用冻结路径：

```text
POST /api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/{analysis_version_id}:submit-review
```

请求必须精确包含 `reviewer_ids/policy_ref/due_at/submission_note`。`reviewer_ids` 为 1～32 个互异 canonical UUID，`policy_ref` 固定为 `HANDOVER_ALL_V1`；由于当前 Review Schema 没有调度时限和提交备注事实，CR-HND-006 要求 `due_at` 与 `submission_note` 在 V1 中显式为 `null`，非空返回 422，不静默丢弃。

成功返回 201、`ETag: "v1"` 和最小 Review/首轮引用：Review、Round、Project、Handover Analysis/Version、策略、评审人、提交人/时间及 `IN_REVIEW`。不返回主题正文、Evidence 内容/路径、AI 输入输出或内部表结构。

## 原子性、安全与幂等

入口要求可信 Origin/Host、当前 Session、私有 CSRF、16～128 字符可打印 ASCII `Idempotency-Key`、有效 License 和当前 ProjectManager。服务在同一个 Unit of Work 中预锁评审人、重验当前项目/Version/来源/Action/评审资格，创建 PROJECT Review identity、第一轮、Audit 和业务收据，末次 License 检查通过后一次提交；任何一步失败整笔回滚。

同 actor/project/operation/key 的同载荷重放恢复不可变第一轮响应，即使 Review 后续已经批准、退回或撤回也不把当前终态伪装成首次响应；重放仍重验当前 ProjectManager 和 Handover Subject 访问。异载荷复用返回 409。可重试数据库死锁最多重做整个 UOW 三次，不能拆分提交。

## 错误、兼容与回滚

权限和资源隔离失败统一 404；License 403；请求形态 400；调度字段、业务送审资格或评审人资格 422；在审锁、版本、归档或幂等冲突 409；未知内部失败 503。错误不回显 SQL、路径、正文、内部异常或 Secret。

本增量无 Schema/Migration/依赖/配置/网络或客户数据外发。Router 只有显式注入时存在，默认和当前 Windows 生产组合仍为 404；A07 才完成正式组合。回滚方式为停止注入 Router，已提交的合法 Review/Audit/收据历史保留。
