# CAP-01-A04-A04：Capability Review 终态正式化

日期：2026-10-05。结论：`CAP_01_A04_A04_TERMINAL_FORMALIZATION_PASS`。下一项：`CAP-01-A05-A01` Capability 冻结HTTP与生产组合前置核查。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A04-A04
输入基线：冻结共同版本状态、DM-05、API-04、Schema0093、CR-CAP-001/CR-RVW-003
前置任务：真实Capability送审锁、GLOBAL Review事务内核已通过
涉及模块：Capability Review Subject/Repository；Version创建条件；Schema0094
涉及实体：CapabilityBaseline、BaselineVersion、Review/ReviewRound终态、Audit
涉及API：无公开HTTP；受信内部组合
涉及权限：终态前重验当前Actor、全部Reviewer及Document/Evidence；Review负责决定资格，Capability负责正式化
验收标准：APPROVED指针原子更新、旧正式版SUPERSEDED、RETURNED/WITHDRAWN保留旧指针、终态后可建新Draft、故障全回滚
风险：孤立APPROVED、双正式版、撤回误批准、首次批准后无法升版、跨Owner半提交
```

## 实现与偏差

Schema0094开放唯一终态路径并以延迟触发器把Version状态、GLOBAL/CAP-01 Review/Round结果及Baseline正式指针绑定；部分唯一索引保证同Baseline最多一个APPROVED。Capability Subject Owner在Review终态写入之后消费结果，并在同事务写Capability Audit；APPROVED更新正式指针并把旧APPROVED改为SUPERSEDED，RETURNED/WITHDRAWN统一把Version记为RETURNED且保持旧指针，Review历史保留两者区别。

核查发现Schema0092时代的Version创建仓储强制正式指针为空，首次批准后将永久无法升版。按冻结“正式旧版保留、修订创建新Version”规则移除该条件；ACTIVE、强ETag和不存在IN_REVIEW的约束保持。该兼容调整与终态正式化不可分割，已记录在Schema0094和DEC-839。

为保持A03历史验证可复现，Subject Owner保留显式`terminal_enabled=False`验证模式；默认生产语义启用终态消费。公开HTTP、Session/CSRF/License/幂等外层仍留A05，不在本项提前挂载。

## 验证

- Windows 11 / PostgreSQL 18.6：空库`0094 -> 0093 -> 0094`、两次Alembic drift、真实首版APPROVED、第二版RETURNED、第三版WITHDRAWN映射RETURNED、第四版APPROVED、旧正式版SUPERSEDED、全过程正式指针/锁版本及4条Capability Audit通过；终态历史拒绝降级。标记`CAP_01_A04_A04_TERMINAL_FORMALIZATION_PASS`。
- A03失败关闭模式在Schema0094 head重新运行通过，证明历史验证语义未被静默改写。
- 首轮实库因同一触发器对Baseline行求值Version专属字段失败；拆分表分支后修复。第二轮发现仓储方法插入位置使终态断言误执行送审锁更新；恢复到`bind_start`后修复。第三轮产品链已通过，仅验证SQL误写Audit表名，修正为`aud_events`后从全新库完整重跑通过。
- 后端全量2559项通过、3项既有条件跳过；开发wheel内Review103项、Capability23项通过，SHA-256 `002abd2f409b96be5f6b6f24a8cb7151a4b4f2cb17e501b9ed7bf58cc54e258a`。
- `compileall`、migration drift与`git diff --check`通过。

## 兼容、迁移、回滚与剩余边界

内部Schema`0093 -> 0094`，无冻结API、依赖、网络、Secret、客户数据或资料自动导入变化。无终态历史可降；有正式指针或终态Version拒降并向前修复。停用后续命令组合可关闭新流量，已提交正式版本和Review/Audit历史不可删除。

当前尚无冻结`CAP_VERSION_SUBMIT_REVIEW` HTTP、Session/CSRF/License/持久幂等外层、读取API、前端和生产组合；真实标准能力内容质量也未因此得到证明。Gate 3、正式信任、性能及目标平台发行证据保持阻塞。
