# REQ-01-A05-A04：Human Decision 与五类固定来源闭环

日期：2026-10-07。结论：`REQ_01_A05_A04_FIXED_SOURCE_CLOSURE_PASS`。下一项：
`REQ-01-A06` RequirementVersion create/list/get。

## 实现与边界

- Requirement 模块新增 Human Decision 专用只读 proof，只接受同项目、同 Requirement 的既有不可变
  `DEFER / REJECT` 决定；在调用方事务内共享锁定决定、首成功命令结果及全部 Evidence 引用。
- proof 重证 operation、reason、impact、前后版本、最终状态和规范排序的 Evidence 集合完全一致；自由文本、
  通用 Review、Handover Action 或不存在的范围/风险决定均不能替代正式决定 Owner。
- 五类 proof 在一个调用方事务中完成闭环：批准 SurveyConclusion、当前批准 Handover、不可变人工决定、
  当前 PROJECT/ELIGIBLE Evidence 和当前 GLOBAL Capability。各 adapter 只返回最小类型化身份，不复制正文、
  locator 或动态 latest，也不自行 commit。
- 人工决定的 Evidence 集合是决定时的不可变历史；Evidence 后续撤销会使当前 PROJECT_EVIDENCE proof
  失败，但不追写或否定已发生决定的历史事实。

## 验证

- Windows 11 / PostgreSQL 18.6：五类 proof 同事务成功；跨项目、决定与首结果 Evidence 集合错配、
  当前 Evidence 撤销和零写均按预期失败关闭；Alembic drift 无新增操作。
- 错配负例保留数据库合法 shape，并替换为错误 Evidence UUID，使失败来自 proof 的精确集合核验，而非
  预先命中数据库非空约束。
- 定向24项、后端全量2992项通过且3项既有环境跳过；开发 wheel 共1137项，SHA-256
  `b50f8a68b831a613232fd6c4fccbb803d830259abe441e653250a08ea174ecd3`，不是正式发行包。

无Schema、Migration、公开API、依赖、Secret、客户数据或外发变化；A06～A12、Gate3/UAT/发行待。
