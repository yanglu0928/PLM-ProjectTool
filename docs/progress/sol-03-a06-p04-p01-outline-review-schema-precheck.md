# SOL-03-A06-P04-P01：Outline 统一 Review 状态窄门编码前核查

日期：2026-10-24。状态：`PRECHECK_PASS`；本项只确定数据库状态边界与实施顺序，未开放送审或批准。

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / `SOL-03-A06-P04-P01` |
| 输入基线 | Gate 2 冻结 DM-05 的 OutlineVersion 固定章节/需求/参考与独立 Review；API-04 `SOL_OUTLINE_VERSION_VALIDATE`、`:submit-review` 仅 ProjectManager；统一 Review Subject 固定送审合同；A05同库三维当前事实验收 |
| 前置 | OutlineVersion创建/读取、DRAFT现时VALIDATE、Section真实Review/Trace及合格Requirement/Section合成链已验；不代表Outline自身可送审 |
| 涉及模块/实体 | solution、review、audit；`sol_outlines`、`sol_outline_versions`、`rvw_*`，预期新增Outline专属Review结果闭合表/受控Guard |
| API/权限 | 本片无API变更；后续送审仍限ProjectManager，客户评审只在统一Review资格Owner确认后可用 |
| 验收标准 | 定位既有阻断、明确唯一合法状态/指针转移、固定Subject/Review/Round/快照一致性、空库与有数据升降级及失败关闭负例 |
| 回滚/风险 | 不可放宽Version内容/子表不可变约束；不可用客户端ReviewRef或历史VALIDATE代替同事务现时资格；有Review历史时禁止破坏性downgrade |

## 代码与基线核查

1. 冻结模型给出Outline逻辑根、不可变Version及独立Review；Outline批准不等于Section正文批准。API-04仅冻结`POST .../versions/{outline_version_id}:submit-review`、ProjectManager与201 ReviewRef/RoundRef，未冻结具体policy code或结果表名。
2. 当前ORM已有Version `DRAFT/IN_REVIEW/APPROVED/RETURNED/SUPERSEDED/RESTRICTED`、Review/Round成对字段和根`current_approved_version_ref`外键。0156的`guard_solution_outline_version_foundation`仍对Version UPDATE一律拒绝，只放行受限DRAFT INSERT；0156不防止同根IN_REVIEW期间继续创建新Version。根的`guard_solution_identity_foundation`仍只放行INSERT；故真实送审/批准没有合法数据库写路径，不能通过关闭触发器绕过。
3. 0183/0184 Section Review采用追加式状态结果、Owner限定Version/根指针转移及统一Review/Round/SubjectSnapshot校验，可复用设计形状但不可直接把Section的SOL-05策略套到Outline。Outline建议固定`SOL-03 / solution_outline_id / solution_outline_version_id`与独立`SOLUTION_OUTLINE_ALL_V1`策略，必须由后续Subject Owner和Review注册显式核验。
4. 需在同一事务锁根/最新Version、Review及Round；DRAFT→IN_REVIEW固定Review/Round，IN_REVIEW→APPROVED或RETURNED保持引用，旧APPROVED仅在新批准时→SUPERSEDED；根批准指针仅指向同根同项目已批准且Review闭合的最新Version。撤回路径应是IN_REVIEW→RETURNED，旧批准指针不变。拒绝旧版/越项目/错Review或Round/错策略/错指纹/静默改写和并发双提交。
5. 数据库设计片需同时更新ORM与Alembic up/down，先检查有数据旧库能否安全升级；空库/有数据升级、旧DRAFT与已有批准历史、降级保护、迁移drift及负例均要验。由于当前没有合法Outline Review历史，不能假设历史数据已符合新规则；发现冲突先登记CR并保留原基线。

## 后续独立顺序

- `SOL-03-A06-P04-P02`：仅建立Outline Review数据库闭合结果与状态Guard；不得在此片顺手开放HTTP。编码前重新确认Schema具体列、触发器替换范围和downgrade条件。
- 后续分别实现Subject现时证明、统一Review原子送审/终态消费、冻结HTTP与Windows显式装配，再跑一次性PG及浏览器。送审/批准时重新证明A05的order/source/coverage全PASS；合成客户结果不得宣传为真实客户确认。

本片为静态只读核查，无程序/Schema/数据变化，未运行新功能测试。Gate 3、Pilot和正式三平台Release仍未通过。
