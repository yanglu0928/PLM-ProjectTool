# OUT-01-A01-P26 编码前检查：Output Generate Job Owner 专属 claim

- 日期：2026-11-05
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P26
- 结果：PASS_WITH_LIMITATION，可进入实现
- Change Request：CR-OUT-022

## 编码前检查

- 当前Phase：Phase 2 Platform Core；Gate 3 尚未通过。
- 当前WBS：OUT-01-A01-P26，仅收紧Jobs中Output生成作业的claim边界。
- 输入基线：冻结Architecture、Data Model、DB Schema V1和API Contract V1；现有Jobs Lease/Job/Attempt模型、Output Job enqueue Owner及CR-OUT-022。不得改变冻结字段、表结构或公开合同。
- 前置任务：OUT-01-A01-P01至P25已有实现；P25 hosted run [41925875768](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41925875768) 已明确失败关闭，且CR-OUT-021第十三轮已登记无效PATH对照及路线切换。P25不阻塞这一独立claim边界工作。
- 涉及模块：Jobs application/infrastructure/tests；Hosted父包PG lifecycle中的专项验证器。Output只通过现有Jobs Queue Port写入作业，不直接访问Jobs表。
- 涉及实体：Job、JobLease、JobAttempt及现有OutputRequest引用；不变更ORM、Migration或持久字段。
- 涉及API：无公开HTTP/API变更；新增内部Jobs专属claim Application Port/Service方法。
- 涉及权限：Worker身份格式与Lease duration沿用Jobs规则；Output claim只接受精确Owner/JobType组合 `output / OUTPUT_GENERATE`。通用claim不得获取该组合；不得削弱现有Plugin/RAG专属边界。
- 验收标准：
  1. `JobLeaseService.claim_next_output` 对worker及lease参数执行与其他专属claim一致的前置校验并委托Output专属Repository调用。
  2. `SqlAlchemyJobLeaseRepository.claim_next_output` 精确限定 `owner_module='output'` 与 `job_type='OUTPUT_GENERATE'`，覆盖待取、重试及到期恢复的共用claim查询。
  3. 通用 `claim_next` 排除精确Output Generate组合；不得误排除其它Owner或同Owner其他JobType。
  4. 单元测试覆盖输入校验/委托；Hosted PG18.6真实验证由generic claim先跳过Output作业、Output claim取得该作业、错误Owner/Type不被混取并保持租约fencing字段一致。
  5. GitHub hosted全链执行；任何失败先记录偏差，不标PASS。
- 风险：Output专属Worker尚未存在；该改动只确保Output job不被错误Worker取走，可能使Output作业继续排队。这是预期的安全失败关闭。无插件执行、文件生成、公开路由、客户数据或生产信任变更。
- 验证环境：仅GitHub hosted Windows Server 2025 runner，检查 `RUNNER_TEMP` 位于D盘，隔离合成PG；不在用户本机/C盘运行代码、安装依赖或测试。
- Secret检查：只新增合成UUID/Job字段；不写凭据、原始环境PATH、客户正文或运行日志。推送前复核变更及workflow摘要无Secret。

## 实施步骤

1. 为Jobs Repository Port、Service及SQL repository增加Output专属claim，并将Output Generate从通用claim可选集合中排除。
2. 扩展现有lease unit test，新增专项输入校验和repository委托断言。
3. 新增独立PG验证器，在父包PG smoke确认PostgreSQL/pgvector可用后调用；只输出Job claim状态、Owner/Type、fencing token布尔/计数结果。
4. hosted全量验证，记录P26结果，并继续评估Output generation真正启动前尚缺的Publisher信任和独立进程运行合同。

## 回滚

撤销专属claim API与条件变化即可恢复源代码；若验证失败，保持Output Generate不被通用Worker消费，不通过放宽claim边界规避失败。无Schema/API迁移。