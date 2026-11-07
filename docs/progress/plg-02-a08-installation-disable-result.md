# PLG-02-A08：PLUGIN_DISABLE 受控 HTTP 命令验收结果

- 日期：2026-11-04
- 状态：`PASS_SCOPE_LIMITED`
- 变更请求：`CR-PLG-013`
- 编码前检查：`docs/progress/plg-02-a08-installation-disable-precheck.md`
- hosted 验收：[GitHub Actions run 41770188317](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41770188317)，13/13 jobs 成功
- 源分支：`feature/p51-a33-launcher-checksum-recovery`
- 最终代码提交：`d45d6d779ea0f9ae1e097c6ffbe942e3d1a6947c`

## 已交付

- 新增冻结 `PLUGIN_DISABLE` 的受控 `POST /api/v1/admin/plugins/installations/{installation_id}:disable` HTTP 路由，空请求体、拒绝 query，执行 Session、License、DeploymentAdmin、Origin/CSRF、强 `If-Match` 与 `Idempotency-Key` 校验。
- 仅显式 Production Platform Write 组合挂载；默认/Login-only/Read/Write Trace 组合不挂载，不触发物理卸载、安装器或插件执行。
- 新增追加式 Migration `20261104_0230` 与不可变 `plg_disable_results` 结果快照，在同一 PostgreSQL 事务提交 Installation 状态、Audit、快照与幂等回执；保留原 Schema V1 冻结提交，不改冻结 API Contract。
- 精确重放读取首次固定结果，即使安装随后改变仍保持首次响应；同 key 不同请求拒绝。结果历史存在时拒绝向下迁移，避免丢失命令记录。

## 托管验证

最终 hosted run 41770188317 全部 13 jobs 成功：

- 后端全量 `3970 tests` 与 wheel 构建通过；前端测试、typecheck、production build 通过。
- GitHub hosted Windows Server 2025 / D 盘 runner-temp 上，PG18 临时库验证 Migration 0230 空库升级、既有库升级、降级/重升、安装历史保护及插件 Schema 追加写入守卫。
- PLUGIN_DISABLE PG18 路径：停用后活动操作数0、状态 `DISABLED`、lock_version 2、两条操作 Audit、一个不可变结果行、一个完成回执；Audit 失败完整回滚，精确幂等重放成功，后续状态变更不改写首次快照，同 key 异载荷冲突，结果行阻止降级；无客户数据或外部调用。
- 同 run 父包为非发行候选：20,180 payload files，ZIP 379,391,299 bytes，SHA-256 `a49af40701da8f5d118ead1873c8d755e7663252750fde330dc01b21ab61dfae`。clean PostgreSQL 生命周期 smoke、A17 PlanVersion Edge/HTTPS/PG、A34离线替换/手动恢复、A35分片交接及A50 Edge来源导航均通过。

## 验收偏差与修复

- 首轮 run [41764475466](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41764475466) 发现 A06 enable 校验误引用 A08 参数、0230 时间戳方言类型不兼容、测试迁移 head/ORM 清单未更新；均先记录 CR，再修复。
- run [41765575181](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41765575181) 和 [41767093675](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41767093675) 依次发现父包迁移验收仍锁定0229、合成数据清理TRUNCATE遗漏结果表，以及历史降级到0222时误用0230触发器数量。各偏差先记入CR，再修正验收器；HEAD 0230 的21个PLG触发器/5个closed-owner guards严格断言保留。最终全链 run 41770188317 通过。

## 限制

本结果仅是 hosted Windows Server 2025 上的合成身份/合成数据自动化证据。未在用户本机或 Windows 11 设备运行；没有启动正式产品 API/数据库/服务，没有正式 License/公钥、目标服务账户凭据、ACL/TLS或法律放行。Pilot 仍 `NOT_READY`，Gate 3 未通过，正式 Release `NOT_READY`。

回滚可撤下路由与显式组合；Migration 0230 的结果历史存在时禁止降级删除，需保留命令记录。
