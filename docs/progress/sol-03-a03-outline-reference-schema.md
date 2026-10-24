# SOL-03-A03：OutlineVersion 固定 ReferenceVersion 关联封闭结构

日期：2026-10-09。结果：`SOL_03_A03_OUTLINE_REFERENCE_SCHEMA_PASS`；仅 Schema/ORM/迁移完成，版本 CREATE/VALIDATE/Review 仍未开放。

## 编码前检查与单一问题

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A03。输入为 Gate2 DM-05/API-04、CR-SOL-002、DEC-20261009-1138、0137～0153、SOL-03-A02、SOL-01-A16 的真实资格机制。
- 本项只填补冻结 OutlineVersion 缺少固定 ReferenceVersion 关联的结构缺口，不顺手解锁业务 Owner 或 HTTP。涉及 Solution OutlineVersion、ReferenceVersion 的 ORM/DB Schema；公开 API/权限均保持不变。
- 验收：空库及既有版本行升级、可逆空历史降级/重升、Schema drift、同项目/GLOBAL 固定引用、顺序/去重、封闭 DML 与历史拒降。风险：FK 不等于当前资格/来源有效；现时性留给下一独立 Owner 同事务证明。

## 实施与兼容性

线性迁移 `0153→0154`：ReferenceVersion 增加 `(Version,Root,Scope,Project)` 唯一键；OutlineVersion 增非负 `declared_reference_count`，旧行默认 0；新建 `sol_outline_reference_refs`，使用版本/根/Scope 基础 FK 和 PROJECT 来源 Project 复合 FK，并对 PROJECT 同目标项目、GLOBAL 无来源项目加 CHECK。版本内序号及目标版本唯一。新表复用 0137 写/截断拒绝 Guard，旧三表 Guard 不动。

回滚：仅新引用表为空且所有目录版本引用计数为 0 时允许 `0154→0153`；已有历史拒降而非丢弃。新表直接写仍失败关闭，不能通过本迁移制造正式目录版本。未改冻结 `/api/v1`、依赖、AI 外发或客户数据。

## 验证与剩余工作

Windows 11 隔离 PostgreSQL 18.6 验证脚本 `validation/sol-03-a03-outline-reference-schema/verify.py`：空库升降重升、既有版本行默认值、四轮 Alembic drift、PROJECT/GLOBAL 合法固定 FK、跨项目/错误目标/重复/非法顺序拒绝、DML/TRUNCATE 拒绝、两类有历史拒降。定向单测 5 项、后端全量 3407 通过/3 跳过/5199 子例（2 条既有警告）。合成上游根仅为约束验证，不代表业务资格批准。

下一独立任务 `SOL-03-A04`：受权 OutlineVersion CREATE Owner/Guard，必须同事务核实当前 APPROVED RequirementVersion、可用 Section、ReferenceRoot 当前 ELIGIBLE 版本及其 Document/Evidence/脱敏现时性、权限、计数与幂等；在该证据前继续阻塞 CREATE。之后仍需 HTTP、Windows、前端/Edge、VALIDATE/Review/Trace/Workflow、质量/性能/正式信任及发行；Gate3 不因此通过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/DEC-1138 → 0137/0153 → 本 0154/验证 → SOL-03-A04 → Gate3。
