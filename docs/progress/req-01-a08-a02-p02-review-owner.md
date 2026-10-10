# REQ-01-A08-A02-P02：Requirement Review Subject Owner

日期：2026-10-07。结论：`REQ_01_A08_A02_P02_REVIEW_OWNER_PASS`。下一项：
`REQ-01-A09-A01` RequirementRelation 编码前核查。

## 实现

- 新增Requirement专属Review Subject Owner与PostgreSQL Repository，复用统一PROJECT Review内核，
  固定`REQ-03 + REQUIREMENT_ALL_V1`，不复制Review状态机。
- Create/Start只接受ACTIVE Root的最新DRAFT且无Review绑定；全部Reviewer通过当前项目成员资格重证。
- Start与APPROVED均在调用方事务内运行A07 CurrentValidator，历史Validate Audit不替代当前事实；任一
  来源、Capability、Evidence、分类或Acceptance问题均失败关闭。
- START/终态依次更新Version和Root并插入Migration0120不可变结果；终态断言重读结果、Root lock、正式
  指针和唯一APPROVED。批准同步SUPERSEDE旧正式版；RETURNED/WITHDRAWN保留旧指针且不要求失效来源
  重新有效，避免无法退出IN_REVIEW。
- 每个终态写`REQUIREMENT_VERSION_<REVIEW_STATE>` Audit。Owner不提交事务、不访问Review外键之外的
  外模块表，任何异常由Review调用方统一回滚。

## 验证

- Windows 11 / PostgreSQL 18.6：最新DRAFT授权、Reviewer资格、START结果、来源漂移阻止批准、恢复后
  批准、第二版本批准并SUPERSEDE旧正式版、第三版本RETURNED且正式指针保持、Root lock连续递增、
  终态Audit及Alembic drift通过。
- 首轮验证最终断言误把既有`REQUIREMENT_VERSION_CREATED`纳入终态Audit集合；收窄夹具查询后从全新
  数据库复跑通过，产品实现和验收规则未改变。
- 定向14项、后端全量3019项通过且3项既有环境跳过；开发wheel共1148项，SHA-256
  `5bd3164b8a43ef9a9252e6ca9b6eb473dc75213513b509046b7d6f1e978d99a1`，不是正式发行包。

无Schema、公开API、依赖、Secret、客户数据或外发变化。停止注册Owner即可关闭新Review入口，既有
Review、Version、不可变结果和Audit继续保留。A08内部能力完成；HTTP/Windows显式组合按计划在A10完成。
