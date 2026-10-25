# CR-PLAN-004：安装PlanVersion不可变聚合Owner的追加写门

日期：2026-10-26。状态：`P03-A01_IMPLEMENTED_PASS_SCOPE_LIMITED; P03-A02_PENDING`；非Gate通过。

## 发现

0170～0176的PlanVersion、WBS、FS依赖、Milestone、Requirement/Solution/Evidence引用均挂载“Owner is not installed”无条件拒写触发器；0186/0187新增的owned rows沿用相同关闭守卫。即使Application service完成授权和幂等，任何INSERT仍会失败。直接删除owner triggers虽能写入，却会失去对子行UPDATE/DELETE的数据库不可变保护；移除TRUNCATE trigger会允许毁坏正式历史。

## 方案

- A：Plan Owner从业务代码执行前移除触发器。拒绝：依赖应用启动顺序、易遗漏且扩大误删/改写历史风险。
- B：0188仅把Owner guards调整为“允许INSERT，拒绝UPDATE/DELETE”，保留全部no-TRUNCATE triggers；PlanVersion发布为只创建新version，不原位修改已有version。downgrade只把guards恢复成无条件拒写，不删函数、表或历史。
- C：完全移除Owner触发器。拒绝：失去版本不可变与依赖/TRUNCATE保护。

选择 B。迁移不增加表/列，不改Gate 2 API或数据；任何成功INSERT仍必须经过Plan Application Owner的Session/CSRF、Project角色、License、source lock/recheck、DAG/coverage校验、事务幂等和Audit。DB guard只负责append-only边界，不冒充授权或来源证明。新增数据后降级0188只是恢复拒写，历史保留。

## 验证计划

- PostgreSQL 18.6 隔离库从0187升级0188，所有指定Plan父/子表允许INSERT但拒绝UPDATE/DELETE/TRUNCATE；downgrade后INSERT也拒绝而原行保留。
- 使用真正Plan DRAFT Owner的完整事务测试成功、重复Key相同快照、不同payload冲突、权限/License/source拒绝和中途Audit/子表失败全回滚；证明拒绝/回滚不留部分WBS。
- 全量后端回归、schema drift、原0170～0187 no-truncate/history行为回归。

## 实施记录（P03-A01）

- Migration `20261026_0188` 已将八个Plan owner guard改为允许INSERT、拒绝UPDATE/DELETE；所有独立TRUNCATE guards保持不变。
- Windows 11 / PostgreSQL 18.6隔离临时库升迁、降迁、重升与Alembic drift检查通过；八个实际PG trigger invocation的INSERT允许及UPDATE/DELETE拒绝、TRUNCATE拒绝、降级闭锁及历史保留均通过。详见 `docs/progress/plan-02-a04-p04-a04-p03-p04-s03-p03-a01.md`。
- 0188不单独投产；P03-A02事务型Owner必须同批受控交付，以封闭开放INSERT的业务写入口。

## 授权与边界

按用户2026-09-24持续授权登记本差异后自主实施；保留Gate 2冻结提交`64cdf09`和历史revision。仅在隔离合成数据库验证，未触碰真实业务数据。Migration 0188与Application Owner须在同一受控交付中完成和验收，不在无Owner前单独部署开放INSERT的迁移。
