# REQ-01-A06-A02：RequirementVersion 原子创建 Owner

日期：2026-10-07。结论：`REQ_01_A06_A02_VERSION_CREATE_PASS`。下一项：
`REQ-01-A06-A03` RequirementVersion 授权 list/get。

## 实现与边界

- 新增完整不可变DRAFT创建服务与SQLAlchemy仓储；只允许ProjectManager、ImplementationMember在ACTIVE
  Requirement上创建。首个版本要求`initial=true`，后续版本的`base_version_ref`必须精确等于当前最高
  Version；Root行锁、显式expected ETag和最高版本共同拒绝并发分叉。
- 同一事务重证当前License/项目角色、A05来源proof及Evidence/Capability，写Root ETag、Version、六类
  owned集合、支持引用、不可变创建结果、Audit和Idempotency receipt；任何失败整体回滚。
- Migration0119开放最小INSERT和ACTIVE Root无字段变化的单次ETag递增；新增不可变创建结果表及两个延迟
  闭包，要求每个Root更新和每个Version都绑定同一首结果。Version及全部子项写后不可改删/截断。
- 内容指纹只覆盖完整规范化业务快照和固定引用；initial/base、expected ETag、client reason进入请求幂等
  指纹但不污染内容指纹。重放重证当前权限和License并返回首次固定结果。
- 因尚无跨Owner原子AI预接纳协议，非空AI Task和`AI_CANDIDATE` assessment均失败关闭；首版只接受
  HUMAN assessment，不能创建无provenance的AI判断。

## 验证

- Windows 11 / PostgreSQL 18.6：Migration0119空库升降重升、Alembic drift、真实Session/角色/License、
  PROJECT Evidence来源、initial/base、Root ETag、幂等、双并发、Audit回滚和跨项目Evidence通过。
- 无结果Root bump、无结果Version直写均在提交时失败；存在创建历史时物理降级拒绝。
- 首轮全量回归仅发现统一ORM metadata归属清单未登记新结果表；补齐Requirement模块显式归属断言后，
  业务代码不变并全量复验通过。
- 定向33项、后端全量3000项通过且3项既有环境跳过；开发wheel共1140项，SHA-256
  `474937eb4ba52d05c61a117649153d8c5074b2e33404e6339cf9d905929b5d78`，不是正式发行包。

Schema head升至0119；无公开API、Secret、客户数据或外发变化。A03、A07～A12、Gate3/UAT/发行待。
