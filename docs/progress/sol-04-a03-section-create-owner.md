# SOL-04-A03：SolutionSection 内部受权 CREATE Owner

日期：2026-10-09。结果：`SOL_04_A03_SECTION_CREATE_OWNER_PASS`，限内部服务、Win11 隔离 PostgreSQL 18.6 与合成 License/用户；不代表公开 HTTP、正式部署或 Gate 3 通过。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-04-A03。
- 输入基线：冻结 `SOL_SECTION_CREATE`、DM-05、CR-SOL-012、0147 快照表、现有 Outline Owner/持久 Receipt/Audit。
- 前置任务：A01 变更登记、A02 ORM/Schema/空及有数据迁移验证通过。
- 模块/实体/API/权限：Solution 内部 Owner/仓储、Project 操作策略、0148 Guard；SolutionSection 身份与首次结果；不挂公开 `/api/v1`；项目 PM/实施成员在有效项目和活动 Outline 下可创建，服务端独立复验。
- 验收标准：固定初态 INSERT 与延迟快照闭合、同事务 Receipt/Audit、同键精确重放与异载荷冲突、同 Outline 重复 key 冲突、权限/License/归档/暂停拒绝、失败回滚、直接 SQL/Version DML 闭锁、空历史回退/有历史拒降、后端全量。
- 风险：伪造数据库凭据的连接仍可能构造合法根/快照双行；0148 Guard 不是数据库级身份授权，正式账户最小权限另验。

## 实施与验证

新增 `SectionCreateService` 与 SQLAlchemy 仓储。输入只含 ProjectId、活动 OutlineId、`section_key`；名称按 NFKC/trim、1..128 与控制字符规则规范化。授权先锁当前项目成员事实，再锁同项目活动 Outline；Receipt 指纹绑定 Project/Outline/key，重放从不可变首次结果恢复；新建在同事务写根、快照、`SOL_SECTION_CREATED` Audit 与 Receipt。重复 key 映射 `CONFLICT_DUPLICATE`，其他数据库错误不披露内部信息。0148 仅开放合规 Section/首次结果 INSERT，保留 Outline 已有操作，关闭所有 UPDATE/DELETE、TRUNCATE 与 SectionVersion；延迟约束拒绝无快照提交。升级时若发现异常既有 Section 记录则停止，要求审计迁移；空历史可回退 0147，有 Section/快照历史拒降。

Win11 一次性 PG18.6：0147→0148 空历史降级重升、Alembic drift，真实 Session/PM/实施成员与项目授权、客户/跨项目/暂停成员/归档项目/归档 Outline/License 拒绝、同 Key/并发重放、不同载荷/重复 key 冲突、Audit 失败回滚、直接 SQL 初态/无快照/错误快照/更新删除/Version INSERT 负例，以及有历史拒降通过。原 PROJECT Reference 夹具回归通过。后端全量 `3386 passed, 3 skipped, 5100 subtests passed`；离线 migration SQL 渲染通过。首次定向失败是离线迁移检查曾在 Python 层查询 DB、Version TRUNCATE 被 FK 先拒；改为执行时 SQL 检查和 Version INSERT Guard 负例后复跑通过。

兼容/升级/回滚：无公开 API、前端、依赖或冻结合同变更；0147→0148 线性迁移与内部 Owner 同交付单元。若发布前关闭，撤下内部调用/路由并把 Guard 保持关闭；已有历史不可降级删除，须向前修复。正式信任源/目标服务账户、Server2025、20并发、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。下一项 `SOL-04-A04` 可选 CREATE HTTP 合同与真实 Session/PG；随后 Windows 显式组合。
