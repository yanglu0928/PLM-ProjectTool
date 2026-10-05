# WFL-01-A07-P07-A03：Workflow Checklist 受权命令与 Handover 策略注册

日期：2026-10-05。结论：`WFL_01_A07_P07_A03_CHECKLIST_SERVICE_PASS`。

## 完成范围

- 新增调用方事务内的 Checklist 受权命令：Session/CSRF 预检、License、ProjectManager-only 授权、持久幂等、Handover Owner、不可变追加与 Audit 作为一笔原子事务。
- 首批仅注册 `HANDOVER_BASELINE` 和 `HANDOVER_ISSUES`；PASS 必须精确匹配 Owner 的 Evidence 集合，FAIL 不伪造资格证明，WAIVED 和其他 Item 失败关闭。
- 冻结请求无 Analysis 身份的兼容问题按 CR-WFL-006 处理：服务端只在项目内恰有一个当前已批准 ACTIVE Handover Analysis 时选择，零个或多个均不确定失败关闭。
- 幂等重放按收据中的 `record_id` 读取当时不可变历史；即使后续已追加更正记录，仍返回原命令的精确回执。
- `REVIEW_ROUND` 证明摘要绑定整个 Handover 资格指纹，包含当前版本、评审、Evidence 和 Action 事实，不仅绑定 Subject 指纹。

## 兼容、偏差与回滚

- 偏差记录：[CR-WFL-006](../changes/CR-WFL-006-handover-qualification-selection.md)。不修改冻结 `/api/v1` URL/DTO，无 Schema/Migration、依赖、Secret、客户数据或外发变化。
- 新增 `WORKFLOW_CHECKLIST_RECORD` 项目授权策略，仅 ProjectManager 可写；这是冻结命令的实现细化，不扩大原角色范围。
- 回滚可停止 Handover 策略注册并撤销内部命令组合；已产生的不可变 Record、Audit 和幂等收据必须保留。

## 验证证据

- 定向34项通过，覆盖授权矩阵、命令、追加、Handover Owner 和当前记录。
- 后端全量：2745项运行、3项按既有条件跳过，0失败。
- Windows 11 / PostgreSQL 18.6：真实 Session/CSRF、ProjectManager 授权、License、精确 Owner Evidence、PASS/FAIL 更正、更正后原 PASS 重放、Audit 故障整笔回滚、同键并发以及零/一/多 Analysis 选择全部通过；资格输出为合成端口夹具，真实 Handover Owner 由 `HND-03-A04` 独立证明。
- Alembic check 无新升级操作。开发 wheel 包含新模块，SHA-256 `62251c2c3672117a63bb1275cd4471eba8a894961bab10dfd404321777e422fc`；仍不是可发行程序包。
- 本项不声称 HTTP、Windows 生产组合、Gate 3、三平台发行或 UAT 通过。

下一项：`WFL-01-A07-P07-A04` 冻结 Checklist 记录 HTTP 合同与安全适配。
