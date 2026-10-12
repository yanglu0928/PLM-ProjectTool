# TRC-01-A03-P03：当前有效 IMPLEMENTS 覆盖证明

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。来源：Gate 2 DM-05/API-04（RequirementVersion → SolutionSectionVersion）、DEC-1194/1197、REQ-03 与 SOL-05 目标 Owner。该证明是 Section 可送审六维中的 Trace 一维前置，不是完整送审结论。
- 范围：Trace 内部证明接收调用方已锁定的 SectionVersion 与固定 RequirementVersion 集合；拒绝空集、重复、异项目、别版、额外/缺失链接。查询仅本项目/目标固定章节/当前 ACTIVE `IMPLEMENTS`，对已读行加共享锁，并逐边重验两端 Owner；返回当前 TraceLink ID 集合。`REVOKED`/`SUPERSEDED` 历史不计覆盖。本服务不读取 Solution 私有表，固定集合必须由 Solution 受权 Owner 传入。
- 验证：定向单元 6 项通过（精确集合、空/缺/多/别版/错误方向或关系、Owner/DB 失败）；Windows 11 一次性 PostgreSQL 18.6 真实 Session、合成已批准需求/五版 Section、受权 Trace CREATE、固定集合 PASS、别版/异项目拒绝、受权 REVOKE 后不再覆盖、重新建 ACTIVE 链后只返回新 Link；Schema drift 检查通过。后端全量 3601 通过、3 跳过、5612 子例；开发 wheel 构建通过。
- 兼容/升级/回滚：无 Schema/Migration、公开 API、权限矩阵、依赖或既有历史变更；新内部证明尚未装入 Section VALIDATE，可撤 Proof/Repository 回滚，真实 Trace 撤销/重建仍保留自身审计历史。
- 限制/下一项：这是查询事务时点的 ACTIVE 集合证明，不是永久批准、客户确认或章内全项目需求覆盖。公开 Trace CREATE/REVOKE 装配和 Section VALIDATE 接线尚待；SOL-06 专项规格/固定引用仍缺，六维 ready_for_review、Gate 3/Pilot/正式发行未通过。合成已批准需求夹具不代表客户签署；正式信任/Server2025/性能未验，Debian13 实机按用户指令跳过。下一项按 DEC-1194 进入 `SOL-06-A01` 专项规格 Schema/Owner 前置核查，再分别实施可验收切片。
