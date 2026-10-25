# A06-P05-P06-P08 PlanVersion 列表冻结接口遗漏纠正与编码前核查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P08`
- 结果：`PRECHECK_PASS_CONTRACT_GAP`

## 证据与纠正

- 复核冻结 `docs/api-contract/api-04-implementation-business-chain-v1-candidate.md` 第 Plan Operation 表，明确列有 `PLAN_VERSION_LIST GET /api/v1/projects/{project_id}/plans/{plan_id}/versions`，权限为 Project member，响应为 immutable version page。
- 当前后端只实现单版本GET、WBS分页和版本写入；无PlanVersion list Application/Repository/HTTP Router/Windows组合。Project Authorization policy也没有`PLAN_VERSION_LIST`，故该冻结Operation目前不可用。
- 先前P06-P05/P06-P07文档将它误述为“冻结合同无列表接口”。保留原记录不覆写；本纠正文件及版本说明明确修订该判断。实现冻结Operation，不新增API、不修改API Contract/Schema。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P08
输入基线：冻结 API-04 PLAN_VERSION_LIST；Plan/PlanVersion 当前ORM；Session/License/Project Authorization；既有Plan/WBS signed keyset cursor约定
前置任务：P06-P04原子SubmitReview HTTP、P06-P06前端写Client、PlanVersion WBS SQL read owner 与 cursor 已完成
涉及模块：Plan application/infrastructure/API、Project authorization、Windows composition、platform API router、验证脚本和合同/单测
涉及实体：Plan、PlanVersion（只读）
涉及API：冻结 GET /api/v1/projects/{project_id}/plans/{plan_id}/versions，page_size/cursor，immutable version page
涉及权限：Session、License、ProjectId+PlanId归属与 PLAN_VERSION_LIST Project-member 权限；默认/未显式读组合不挂载
验收标准：稳定降序 keyset分页/同版本不重复；合法多页；篡改、跨Session/Project/Plan/page_size cursor失败；匿名、无权、许可错误和跨Plan资源不可见；Win11/PG隔离HTTP及默认404；后端全量/开发wheel
风险：此前后端WBS游标已按DEC-20261026-PLAN-WBS-CURSOR-01复用当前账户Vault Plan HMAC key；PlanVersion list采用独立payload family并绑定Session摘要、Project、Plan及page_size，不新增客户密钥/Secret引用；回滚为取消路由装配，不改数据库历史
```

## 实施决策

- 新增只读List service/repository和严格最小版本摘要DTO；版本号降序用于稳定keyset，cursor绑定范围。
- 同时补上`PLAN_VERSION_LIST` authorization policy和明确Windows只读组合装配；默认模式保持404，不挂到Login-only。
- 沿用现有Plan cursor key与独立HMAC cursor family；此为实现层复用，风险/回退/验证和参考既有DEC-20261026-PLAN-WBS-CURSOR-01，追加本次决策日志，不新增/轮换密钥。
- 后续PlanVersion创建/读回UI改排到下一WBS，消费已存在的冻结列表端点；不得依客户端本地猜测拼接历史。

## 验收边界

- 只读Operation，无 ORM/Schema/Migration/业务数据变化；所有SQL须项目及Plan双归属过滤。
- 本项通过只代表冻结读取Contract内部实现验收，不代表真实生产License信任、真实客户来源、Gate、Pilot或Release通过。
