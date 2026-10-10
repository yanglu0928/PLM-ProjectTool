# SOL-02-A06-P01 SolutionOutline 详情读取 Owner

日期：2026-10-09。状态：内部 Owner 在 Windows 11 隔离 PostgreSQL 18.6 验证通过；公开 HTTP、列表分页、正式信任源、性能与发行未验。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P01。
- 输入基线：Gate 2 冻结 API-04 `SOL_OUTLINE_GET`、DM-05 SolutionOutline/OutlineVersion；现有迁移 0146 和 SOL-02-A03～A05。
- 前置任务：CREATE 根身份及同事务结果快照已验；项目读授权、Session/License Guard 和隔离 PG 夹具可复用。
- 涉及模块/实体/API/权限：Solution 读取 Owner、Project 授权、Auth Session、License Guard；SolutionOutline 与 approved OutlineVersion 指针；冻结详情 GET 尚未公开挂载；Project 当前成员可读。
- 验收标准：有效 Session/License、同项目成员可读；未签发 Session、撤销成员、跨项目/不存在对象及 License 失败关闭；未批准根保留空指针；异常审批指针不得误报为已批准。
- 风险：历史 Schema 只保证指针归属，不保证被指版本处于 APPROVED，故读取层需复验状态及 Review 引用；没有正式审批版本时不推断批准事实。

## 实施与边界

新增 `OutlineReadService` 与 `SqlAlchemyOutlineReadRepository`，对根记录执行同项目限定和共享读锁。当前批准指针为空时仅返回目录身份；非空时，仓储要求关联版本同根/同项目、`APPROVED` 且存在 Review/round 引用，否则失败关闭。返回身份、状态、批准指针、创建者/时间及根强 ETag，不返回未审批内容。新增独立 `SOL_OUTLINE_GET` 全项目成员只读权限；未修改 Schema、迁移或冻结 API。

## 验证与追溯

- 定向单元：12 passed / 707 subtests，覆盖权限矩阵、Session/License、缺失、伪造投影和仓储指针防线。
- Windows 11 隔离 PG 18.6：真实 CREATE→详情、PM/IM 成员、跨项目、未签发 Session、不存在、License 拒绝、暂停成员及空批准指针通过；临时数据库/进程按夹具清理。
- 全量回归：3369 passed / 3 skipped / 5032 subtests passed。
- 当前无法通过正常业务命令产生正式 Approved OutlineVersion；非空指针的正/负真实 PG 路径须待版本审批 Owner 独立实现后复验，不把静态读取防线当完整审批链 PASS。

下一项：`SOL-02-A06-P02` 可选详情 GET HTTP 合同与真实 Session/PG 验证。列表分页单独推进。
