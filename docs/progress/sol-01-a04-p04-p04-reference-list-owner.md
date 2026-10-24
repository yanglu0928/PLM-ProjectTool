# SOL-01-A04-P04-P04：PROJECT Reference 列表读取 Owner

日期：2026-10-09；结果：`REFERENCE_LIST_OWNER_PG_PASS`。仅内部项目列表服务/仓储，公开 List HTTP 和 Windows 组合尚未开放。

```text
当前 Phase：Phase 2 Platform Core
输入基线：Gate 2 API-04 SOL_REFERENCE_LIST、P04-P01～P03、DEC-20261009-1114
前置：Reference 当前版本 GET Owner/HTTP/Windows 合成验证通过
涉及模块/实体：Solution Reference Root/CurrentVersion，Project Authorization
涉及 API：无公开路由变化；后续 List HTTP 使用本 Owner
权限：有效 License、当前 Session、同项目 ACTIVE 成员；独立 SOL_REFERENCE_LIST 策略
验收：稳定 keyset、完整分页、跨项目/暂停/License/错误页面失败关闭、PG/全量回归
风险：公开 cursor 签名与目标账户密钥、List HTTP/UI、20并发待
```

内部列表按 `reference_solution_id` 升序 keyset，限定每页 1～100，返回当前版本身份、名称、Eligibility 摘要、版本号/状态、创建时间及 ETag，不返回 Document/Evidence 明细或原文。根行先按项目筛选和分页，再左连接当前版本并验证归属；缺失/错 Scope/外项目当前版本失败关闭，不因内连接或筛选丢失异常根行。公开游标将另行签名并绑定身份/项目/查询；原始 `after_reference_solution_id` 不直接给用户作为可伪造 cursor。该选择记录 `DEC-20261009-1115`。

Windows 11 独立 PostgreSQL 18.6/私有文件组合验证两条 PROJECT Reference 完整页与 1 项双页遍历、PM/IM/客户成员、跨项目/暂停成员拒绝，来源/创建和 Alembic drift 回归通过。定向 `13 passed, 706 subtests passed`；后端全量 `3315 passed, 3 skipped, 4883 subtests passed`。无 Schema/迁移/依赖/公开 API 变动；可撤内部列表 Owner 回滚，历史数据不变。正式 License/目标账户、Windows Server 2025、Debian 13、20 并发、List HTTP/UI、Gate3/发行未通过。

TraceLink：API-04/DEC-1114 → DEC-1115 → ReferenceReadService.list_current/SqlAlchemyReferenceReadRepository.list_current → 单元/隔离 PG 验证。
