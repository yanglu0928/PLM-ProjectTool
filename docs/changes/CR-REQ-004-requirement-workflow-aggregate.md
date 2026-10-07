# CR-REQ-004：Requirement Workflow 多正式版本聚合资格

日期：2026-10-08。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交
`64cdf09`、六阶段定义V1与既有Handover/Survey资格历史均保留。

## 冲突与风险

`REQUIREMENT_FORMAL_VERSIONS/REQUIREMENT_ACCEPTANCE`要求核验项目实施范围内的全部正式需求；一个项目
可以同时存在多个ACTIVE Requirement及不同的Approved RequirementVersion/ReviewRound。现有Workflow
通用资格合同只容纳一个subject/version/review，并要求两个Checklist item共享同一单Subject coherence。
若直接复用，会发生以下任一错误：只核验一个需求、制造不存在的“项目需求汇总审批”、或把多个独立
Review压成一个UUID。三者都会把不完整范围伪装为Gate事实。

RequirementPackage在冻结模型中只组织同项目Requirement，移除成员不删除需求；它不是项目Scope审批
Owner。因此不能靠选择某个Package静默排除未入包Requirement。Requirement的ARCHIVE命令也不携带范围
决定Evidence，不能单独满足“范围缺口有明确人工决定而非静默删除”。

## 方案比较与选择

- 方案A：选择任意一个Approved RequirementVersion代表阶段。拒绝，无法覆盖项目范围。
- 方案B：生成合成Project Requirement Subject并复用一个Review。拒绝，仓库没有该业务实体、固定版本或
  Review Subject Owner，会伪造批准。
- 方案C（采用）：为Workflow内部合同增加显式多Subject资格集合；保留现有单Subject类型及Handover/
  Survey响应不变。Requirement两个Checklist item返回同一套、稳定排序的正式Version与ReviewRound集合，
  各项仍由真实`REQ-03 + REQUIREMENT_ALL_V1`批准事实证明。

## 事实映射

项目范围按全部Requirement身份计算，不以Package成员关系缩窄：

1. 至少一个ACTIVE Requirement；每个ACTIVE Root必须指向当前Approved Version，且最高版本就是该正式
   版本，不允许尚未处理的DRAFT/IN_REVIEW/RETURNED新版本与“范围已冻结”并存。
2. 每个正式Version重新运行A07当前事实验证：来源、分类、能力人工确认、双侧Evidence及声明集合均无
   issue；`PENDING_CONFIRMATION`永不合格。
3. `REQUIREMENT_FORMAL_VERSIONS`证明完整正式Version集合、各自精确Approved ReviewRound和固定Evidence。
4. `REQUIREMENT_ACCEPTANCE`在同一集合上额外要求每项至少一个完整五要素AcceptanceCriterion，并保留
   Source引用作为反向来源Trace；不得用空标准、AI建议或仅有历史Validate报告替代。
5. DEFERRED/REJECTED Requirement必须有A03不可变决定及当前可用项目Evidence；ARCHIVED Requirement只有
   在归档前已存在DEFER/REJECT正式决定时才算范围已解释，直接从ACTIVE归档将继续阻断资格。
6. 两个Checklist item的聚合集合指纹、正式Version集合和ReviewRound集合必须一致；资格在调用方事务内
   重证并持锁。空项目、多个未决版本、证据漂移、Review漂移或集合变化均失败关闭。

## 兼容、迁移、回滚与验证

- 不修改六阶段Definition V1、冻结Requirement/Review API或既有数据库Schema；资格Preview为
  REQUIREMENT增加独立响应变体，保留Handover/Survey逐字段兼容。
- Checklist写入仍使用已有复数`evidence_refs/review_round_refs`；Stage Transition新增且仅新增
  `REQUIREMENT → PROTOTYPE`，不跳阶段。
- 回滚时停止Requirement资格注册和PROTOTYPE推进；已写Checklist/Transition历史保留，不降级或改写。
- 分步验证：聚合集合合同与旧Owner兼容、Requirement current-fact Owner、服务/HTTP/Windows接线、
  Windows 11/PostgreSQL 18.6并发/漂移/重放、前端与真实Edge。Windows Server 2025另验；Debian 13按
  用户指令跳过。不得用单元测试或合成状态宣称Gate 3通过。

