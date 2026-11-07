# OUT-01-A01-P29：Output 生成启动原子事务验证结果

- 日期：2026-11-05
- Change Request：[CR-OUT-025](../changes/CR-OUT-025-output-generation-start-transition.md)
- 结论：PASS_SCOPE_LIMITED
- 证据：GitHub Actions [run 41953529123](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41953529123)，Hosted Windows Server 2025 / D盘 runner temp / 隔离 PostgreSQL 18.6

## 实施与验证

- Output Owner按OutputRequest→Jobs一致锁顺序，在同一UOW先锁定精确绑定的QUEUED请求，再由Jobs repository proof校验当前worker、lease、attempt、fencing token和数据库时钟。
- 通过后同事务将请求推进到GENERATING、设置确定性execution ref、递增lock_version并写SYSTEM Audit。Audit actor为显式内部system_actor_id，original_actor_id保留原requester。
- PG18验证有效claim成功；错worker、真实过期前序fencing token、错request绑定均拒绝且无部分状态；同一claim重放幂等且不重复Audit；注入Audit失败时整个Output转换回滚。
- Job保持RUNNING；proof不改Job状态。无Schema、Migration、API或默认应用挂载变化；未执行Worker/插件/渲染/外部调用或输出文件。
- 后端4036项全量单测、wheel、前端测试/build、PG18/pgvector sidecar通过；父包PG smoke、A17、A34、A35、A50成功。

## 偏差与处理

- 初稿锁序Jobs→Output会与取消路径Output→Jobs冲突，已先记CR并统一为Output→Jobs。
- 前三轮hosted偏差均在CR记录并修正：结果字典字面量换行、fixture数量解包、旧token测试未实际替换ClaimedJob。第四轮全部验证通过，前三轮历史保留。
- 本轮独立P25 HTTP/Edge仍因initdb.exe 0xC0000135失败；它不影响本隔离PG Owner验收，也不能描述成P25通过。

## 边界与后续

本结果只证明内部原子状态Owner和审计行为；真实Output Worker、受控服务账号、插件信任、文件产物、Windows 11实际设备、Pilot/Gate/正式Release不因此通过。下一项应先按CR-EXEC-002和当前Worker/Trust阻断建立编码前检查，避免把GENERATING当作执行授权。

