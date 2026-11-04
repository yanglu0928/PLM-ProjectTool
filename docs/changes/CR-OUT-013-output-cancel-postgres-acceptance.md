# CR-OUT-013：OutputRequest Cancel Owner 的 PostgreSQL 18事务验收

- 日期：2026-11-04
- 状态：编码前检查通过，P17实施中
- 来源：CR-OUT-012 P16结果及Output取消Owner真实数据库验收缺口
- 基线：不改变冻结API、Schema、Migration、权限或取消状态语义；所有行只使用新建的合成Hosted临时数据库

## 问题

P16后端全量4,006项、wheel及Parent/A17/A34流程成功，但新 `SqlAlchemyOutputRequestCancelRepository` 与 `SqlAlchemyOutputJobCancellationRepository` 没有直接在PG18正/负行数据执行。OutputRequest CANCELLED 完成时间使用了Application主机时钟，不能保证与DB statement_timestamp一致。

## 方案

在现有Windows hosted `smoke_windows_parent_package_pg_cloud.py` 临时PG18生命周期检查中追加专用验证器 `validation/out-01-a01-p17-cancel-owner/verify.py`。该验证器只对当前run的loopback临时数据库创建隔离synthetic schema/database fixtures，经SQLAlchemy正式Output/Jobs Repositories和Service验证；成功/失败均由现有hosted job清理数据库。测试用合成Session、License、Audit失败注入，不读本机/客户材料、不调用AI/外部API。

覆盖：真实Create Owner建立请求/Job；PENDING立即取消的双行同事务转换；RUNNING有效Lease/Attempt转换为双方CANCEL_REQUESTED但不伪报Worker终止；同Key并发重试只写一份Audit/receipt且返回当前状态；过期Output If-Match不触碰Job；跨Project、错误Job source绑定与无权角色失败关闭；Audit故障回滚Output/Job/receipt/Audit。对CANCELLED输出完成时间使用PG `clock_timestamp()`，flush/refresh后返回持久lock_version。

## 兼容/回滚

无Schema、数据格式、依赖/API Contract变化。OutputRepository保留原方法签名，内部只改时间戳数据源；删除新增验证器调用和脚本即可回滚Hosted验收。数据库Clock修正如有问题，可恢复原注入完成时间；只涉及新的取消状态写入，不改历史记录。

## 验收计划

- 先提交验证器静态测试与Smoke集成点；只在GitHub hosted workflow执行。
- hosted Windows runner临时PG18.6/pgvector执行完整迁移后实际Service/Repository正负事务用例；断言失败回滚后精确比较Output、Job、Lease、Audit和幂等receipt行。
- 完整Backend 4,006+回归/wheel与全仓cloud workflow复验；扫描diff中密码、API Key、License私钥、客户数据和本机配置。
- 若新PG验证暴露状态/trigger行为不兼容，先把客观偏差写入本CR再修复；不得降级断言或伪报Gate/Pilot/Release。

## 编码前结论

现有PG smoke已先建临时数据库、升级迁移并运行真实Output Create Owner validator，且已有失败Audit回滚校验模式；可将P17验证器加入同一D盘Runner临时生命周期。此动作仅验收新Owner专有数据库边界，不表示默认生产应用组合、真实Output Worker或正式Pilot已就绪。
