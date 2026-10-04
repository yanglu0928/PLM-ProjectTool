# HND-02-A03-A04：Action START Owner

日期：2026-10-05。结论：`HND_02_A03_A04_ACTION_START_PASS`。下一项：`HND-02-A03-A05` Action SUBMIT Owner。

## 实施结果

- assigned owner或ProjectManager可在强ETag匹配时把Action从OPEN推进到IN_PROGRESS；其他项目成员按不可枚举资源拒绝，已进入IN_PROGRESS的Action不能再次START。
- START追加唯一`OPEN -> IN_PROGRESS`事件并同步推进Root版本；事件、Audit和actor/project/operation/key作用域的持久幂等收据在同一事务提交。
- 同Key同载荷精确返回首次事件的状态、时间和ETag；同Key不同载荷冲突。重放仍重验当前Session、CSRF、License、项目成员与当前Owner/PM权限。
- 无Migration、公开HTTP、依赖、配置或外发变化；复用Schema0100和CR-HND-003锁定的状态边界。

## 验证

- Win11/PostgreSQL 18.6真实临时库验证通过：owner/PM授权、非Owner隐藏、旧ETag、重复START拒绝、并发同Key单写、幂等冲突、Audit失败整笔回滚恢复及License拒绝。
- 定向17项，后端2634项通过/3跳过；wheel解包17项通过，SHA-256 `fb0cde735e209e1601b8b5c63c03cc1f9770b2af457ec2b274940653e06de83a`。
- 验证偏差：首轮PG夹具遗漏必填`due_at`，第二轮误写收据表名，均未产生有效通过证据，修正后以全新临时库重跑；wheel直接ZIP导入使3项迁移测试无法用`pathlib`读取包内路径，已改为解包后完整重跑17项通过。产品实现未因这些夹具/执行方式问题调整。
- 无公开HTTP、网络或外发；SUBMIT及后续Owner仍待，Gate 3继续BLOCKED。
