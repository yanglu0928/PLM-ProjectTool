# SUR-01-A04-A01：SurveyVersion PROJECT Review 前置核查

日期：2026-10-06。结论：`SUR_01_A04_A01_REVIEW_PRECHECK_PASS`。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：SUR-01-A04-A01
输入基线：冻结DM-05/API-02/API-04、Schema0034/0035/0103/0104、CR-SUR-001、DEC-918
前置任务：Survey identity、完整DRAFT Version及Validate Owner已通过
涉及模块：survey、review、project、audit及四类来源Owner
涉及实体：SRV-01/SRV-02、RVW-01/RVW-02
涉及API：本项不开放HTTP，不修改冻结Operation
涉及权限：送审者ProjectManager；Reviewer为当前合格Project成员
验收标准：核清Subject锁、状态迁移、来源重证、终态正式指针和回滚边界
风险：把历史Validate回执当当前证明；Review已终态而Survey未原子消费；批准后无法创建下一版
```

## 核查结果

1. 通用 PROJECT Review 已具备创建、开轮、决定、撤回、Subject锁、终态回调、Audit与持久幂等内核；`SRV-02`满足现有Subject Type格式，不需要第二套Review表或状态机。
2. Survey 尚未注册 `SRV-02` Subject Owner。默认 Review 组合对未知Subject失败关闭，当前不存在伪送审入口。
3. Migration 0104 只开放DRAFT创建需要的Root `lock_version + 1`，仍拒绝任何Version状态/Review引用更新及批准指针变化。需新增0105窄门，不能绕过数据库守卫。
4. Survey定义没有Handover Action等额外Root前置，可直接进入Review。但送审和批准前必须在调用方事务内重建不可变快照并重新验证题型、条件、指纹、计数、四类来源和目标部门；既有Validate Audit只是历史报告，不能替代当前证明。
5. Review批准只正式化固定SurveyVersion：新版本置APPROVED、旧正式版置SUPERSEDED、Root指针更新；RETURN/WITHDRAW映射RETURNED并保留旧指针。问题内容继续不可变，无逐题状态投影。
6. 创建仓储已禁止存在IN_REVIEW时创建新Draft；0104已允许保留既有批准指针创建下一版，因此批准后升版不存在Capability/Handover曾出现的兼容缺口。

## 实施拆分与验证

- `SUR-01-A04-A02-P01`：Migration0105，开放并延迟校验DRAFT→IN_REVIEW→APPROVED/RETURNED、旧版SUPERSEDED和Root正式指针。
- `SUR-01-A04-A02-P02`：实现真实Survey Review Subject Owner与Repository，复用通用PROJECT Review内核，使用政策`SURVEY_ALL_V1`。
- 后续独立接业务送审HTTP、Windows显式写组合和真实浏览器闭环，不在本前置任务提前扩大。

本项为静态核查，无程序、Schema、Migration、依赖、网络、Secret或数据外发变化。已交叉核对Review合同/仓储、Handover与Capability真实Owner、Survey0103/0104、创建与Validate实现；Gate 3继续阻塞。
