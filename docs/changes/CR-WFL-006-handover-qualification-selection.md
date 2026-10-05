# CR-WFL-006：Checklist 写入的 Handover 资格对象服务端唯一选择

日期：2026-10-05；来源：`WFL-01-A07-P07-A03` 编码前核查；状态：`IMPLEMENTED_INTERNAL / HTTP_PENDING`。原 Gate 2 冻结提交 `64cdf09`、API-02 和 CR-WFL-004/005 保留不改写。

## 偏差与原因

冻结 `ChecklistRecordRequest` 只有 `result/reason/impact/evidence_refs/exception_refs`，没有 `handover_analysis_id`；真实 Handover 资格 Owner 必须绑定具体 Analysis、当前 APPROVED Version/Review 和关联 Action。允许客户端补交或猜测 Analysis 会扩大公开合同并把业务事实选择权交给不可信请求；项目内又允许存在多个 Analysis，不能默认取最新一条。

## 采用方案

- 不修改冻结 `/api/v1` 请求字段。Handover 模块在调用方事务内按 Project 读取并共享锁定所有 `ACTIVE + current_approved_version_ref IS NOT NULL` 的 Analysis。
- 只有候选恰为一条时才把其身份交给既有资格 Owner 重证；零条或多条统一返回资格不可用，不泄露候选数量或身份。
- Workflow 仍只消费 Handover Application Port，不直查 `hnd_*`；客户端 `evidence_refs` 必须与 Owner 输出精确一致。
- 本规则只注册 `HANDOVER_BASELINE/HANDOVER_ISSUES`。WAIVED 和其他 Checklist Item 保持失败关闭。

## 影响、风险与兼容

- 无Schema/Migration、冻结 URL/DTO、依赖、角色、Secret、客户数据或外发变化；新增内部选择方法和受权服务。
- 风险：项目同时保留多个当前批准且 ACTIVE 的 Analysis 时写入会被阻断。该阻断优于非确定选择；后续若业务需要并行基线，必须另行 CR 定义服务端 current pointer 或 V2 合同。
- 历史 Record 不改写；选择发生在每次新命令的当前事务内，幂等重放只读取原不可变结果。

## 迁移、回滚与验证计划

- 数据迁移：无。
- 回滚：停止 Handover 策略注册并撤销内部唯一选择入口；公开API仍关闭/不变，既有不可变 Record、Audit 和幂等收据保留。
- 验证：单元覆盖零/一/多候选、请求引用精确匹配、WAIVED/未注册拒绝；PostgreSQL 18 覆盖真实事务内唯一选择、幂等原结果、Audit失败整笔回滚与并发；后续HTTP/Windows组合独立验收。

## 实施结果

- 已于 `WFL-01-A07-P07-A03` 实现内部唯一选择、Handover 策略注册、受权命令、幂等原历史 Record 重放和 Audit 原子性。
- Windows 11 / PostgreSQL 18.6 实库验证覆盖零/一/多候选、同键并发、更正后原回执重放及 Audit 失败回滚；后续仅剩冻结 HTTP 适配和 Windows 生产组合的独立验收。
