# SOL-01-A04-P04-P01：PROJECT Reference 当前版本读取 Owner

日期：2026-10-09；结果：`REFERENCE_READ_OWNER_PG_PASS`。本项仅实现内部当前版本读取，不代表 GET/List HTTP、页面或生产发行通过。

```text
当前 Phase：Phase 2 Platform Core
输入基线：Gate 2 API-04、CR-SOL-007、Reference Schema 0139/0143/0144、P03-P02-P05
任务：PROJECT Reference 当前版本及固定 DocumentVersion/Evidence 引用读取
权限：有效 License、当前 Session、同项目有效成员；读取不赋予创建或人工确认权
数据：Root 当前指针/Version、全部有序固定引用、来源 Scope/Project、指纹及 ETag
变更：内部服务、仓储及 PROJECT 读取策略；无 Schema、公开 API、依赖变化
```

读取在同一事务内校验当前项目身份与成员状态、Reference 根/当前版本归属及所有固定引用。仓储读取全部引用后核对声明数量、连续序号和每条来源的 PROJECT/ProjectId；不能通过查询过滤隐藏混入的 GLOBAL/外项目行。返回的是创建时固定的身份和指纹，不读取文件正文，也不把历史引用重新解释成来源当前有效或 AI/人工确认的正式业务事实。该边界记录于 `DEC-20261009-1114`。

Windows 11 独立 PostgreSQL 18.6/私有文件组合通过：PM、实施成员、客户成员读取；跨项目、缺记录、暂停成员拒绝；特权注入 GLOBAL DocumentVersion 引用后读取失败关闭。前序 PROJECT Reference HTTP/PG 创建脚本复验通过；后端全量 `3309 passed, 3 skipped, 4858 subtests passed`。本轮未运行 Windows Server 2025、Debian 13，也未验证正式 License 信任源、GET/List HTTP、UI、来源实时资格、20 并发或 Gate 3。下一任务 `SOL-01-A04-P04-P02` 为受控 GET HTTP 合同及真实 ASGI/PG 验证。

TraceLink：API-04/CR-SOL-007 → DEC-20261009-1114 → ReferenceReadService/SqlAlchemyReferenceReadRepository → 单元及隔离 PG 验证。
