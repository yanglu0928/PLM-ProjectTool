# REQ-01-A04-A02：RequirementVersion primary Schema

日期：2026-10-07。结论：`REQ_01_A04_A02_VERSION_PRIMARY_PASS`。下一项：
`REQ-01-A04-A03` 六类版本 owned 语义表。

## 实现与边界

- 新增 `req_requirement_versions` ORM 与 Migration0116，固定 Requirement/Project 归属、正整数版本号、
  DRAFT/IN_REVIEW/APPROVED/RETURNED/SUPERSEDED/RESTRICTED 状态、正文/理由/领域/优先级/风险/分类、
  32字节内容指纹、七类声明计数、替代版本、Review/Round、创建人和创建时间。
- 版本号在同 Requirement 内唯一；替代引用以 Version/Requirement/Project 三列复合外键固定为同一父
  Requirement、同一 Project，并禁止自替代。每个 Requirement 最多一个 IN_REVIEW 和一个 APPROVED。
- `Requirement.current_approved_version_ref` 增加 Version/Requirement/Project 复合外键，不能跨 Requirement
  或 Project 指向版本。A08正式化 Owner 完成前，既有 Root 守卫仍禁止修改该指针。
- `title` 按 DEC-980 保留 nullable 物理列，不改变冻结 V1 最小请求；六类 owned 数据和 AI/Evidence支持
  引用分别留在A03/A04。Version写Owner本项全部关闭，不制造DRAFT或APPROVED业务事实。
- 空 Version 历史可回退0115；存在任一版本后拒绝物理降级，必须向前修复或备份恢复。

## 验证

- Windows 11 / PostgreSQL 18.6：0115→head→0115→head、两次Alembic drift、字段/约束/复合外键、
  partial unique indexes、自替代负例、直接写入拒绝、CASCADE TRUNCATE拒绝和有历史降级拒绝通过；临时库
  已清理。管理员临时停用Owner触发器只用于构造降级保护fixture，随后恢复，不开放产品写路径。
- 定向16项、后端全量2981项通过，3项既有环境跳过；开发wheel共1125项，SHA-256
  `2817b65161453c5ba52d1d0feea5b65716c303a6489629bd1890051c212f54c2`，不是正式发行包。
- 首次从仓库根使用`unittest discover -t .`受中文路径可导入判定影响退出1，按仓库既有方法改在
  `apps/backend`执行完整发现后通过；首次直接TRUNCATE先被反向外键拦截，改用CASCADE到达表级保护
  触发器后验证通过。两次均未作为PASS，修正后重新执行全量验证。

无公开API、前端、依赖、Secret、客户数据或外发变化；A03/A04、A05～A12、Gate3/UAT/发行仍待完成。
