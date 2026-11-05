# CR-OUT-024：Output Job 活动租约与 fencing 证明

- 日期：2026-11-05
- 来源：CR-OUT-023结果；继续建立未来Output Worker的副作用前Jobs安全边界
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P28
- 类型：Jobs Owner内部只读proof；无Schema/Migration/API/默认启动变更
- 状态：编码前检查 PASS_WITH_LIMITATION；允许实施

## 现状与范围

当前Repository私有 _current 查询已锁定Job、活动JobLease及当前Attempt，并校验RUNNING、worker_ref和fencing token；Output没有专属调用入口，且调用方无法获得清晰的Output专属证明。本WBS新增Jobs Owner claim_next_output的配套 check_output_claim：
- 只接受匹配 output/OUTPUT_GENERATE 的当前Job；
- 在一个短事务中使用DB时间核对活动Lease未过期、Job与Lease expires一致、Attempt属于同一worker/token/attempt且未完成；
- 返回现有ClaimedJob身份与fencing信息，不改状态、不续期、不执行外部工作。
- 错worker、旧token、已过期/完成Attempt、其它Owner/JobType全部失败关闭。

本证明仅说明事务读取时租约有效，不能保证事务结束后的租约持续有效；未来Worker必须靠短租约/心跳及每个副作用边界的fencing写入处理竞态。P28不添加Worker、不处理Output状态推进、不调用插件、不生成文件。

## 风险、恢复、验收

- 风险：把读取时有效租约误当成后续永久授权。API名称与返回只表达当前claim proof；后续实施边界需重新确认当前token并使用Jobs-owned fencing事务。
- 回滚：删除专属service/repository入口和对应测试即可；数据库无变更。
- 验证：unit测试输入校验；Hosted PG18用synthetic Output Job检验有效proof、错worker/旧token/其他Owner拒绝和DB时间过期拒绝。后端全量与父包PG smoke在GitHub hosted runner D盘运行。
- 不涉及客户数据、正式Publisher key、外部调用、生产写入或本机/C盘运行。
