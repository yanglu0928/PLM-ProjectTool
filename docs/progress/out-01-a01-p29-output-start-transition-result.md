# OUT-01-A01-P29：Output 生成启动原子事务验证记录（待云端验收）

- 日期：2026-11-05
- Change Request：CR-OUT-025
- 状态：代码及托管验证已提交；GitHub Actions run 41947921582 pending，尚未 PASS

## 实施内容

- Output Owner 按OutputRequest→Jobs一致锁顺序，在同一UOW先锁定绑定的QUEUED请求，再调用Jobs Repository当前lease proof。
- 只有当前Job、worker、fencing token、attempt和数据库到期校验均通过时，才把请求改为GENERATING并设置稳定execution ref及lock_version，随后写SYSTEM Audit。
- system_actor_id由内部组合注入，Audit original_actor_id取请求原始用户；不会将用户标记为worker。
- 同fencing token的相同execution重放只返回现有结果且不重复写Audit。
- 单测及hosted PG18 verifier覆盖正确启动、错worker、旧token、request错绑、精确重放、Audit失败整笔回滚及Job状态不被proof改写。
- 不新增Schema/Migration/API/default app挂载；不启动Worker、不执行插件/渲染/外部调用、不生成输出文件。

## 偏差记录

CR-OUT-025初稿按Jobs→Output锁定；并发取消路径按Output→Jobs锁定，反向顺序可能造成数据库死锁。已在编码前更新CR并改成Output→Jobs，以匹配已有取消Owner。撤销新Owner/Repository/测试为回滚方式。

## 验收边界

云端Hosted Windows Server 2025，runner临时目录D盘；验收使用隔离合成PostgreSQL。验证当前尚未完成，不将预期当作通过。P25 initdb 0xC0000135问题保持独立，不将其作为P29结论依据。真实Worker/受控服务账号、正式信任和Windows 11新设备验收不在本WBS内。
