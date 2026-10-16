# HND-03-A01：Handover Workflow 资格适配前置核查

日期：2026-10-05。结论：`HND_03_A01_WORKFLOW_QUALIFICATION_PRECHECK_PASS`。下一项：`HND-03-A02` Handover 两项 Checklist 资格领域合同。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core，Gate 3保持BLOCKED
当前WBS：HND-03-A01
输入基线：冻结DM-02/DM-05、API-02、六阶段Workflow V1、CR-WFL-003/004/005、HND-01/HND-02运行成果
前置任务：HND Analysis/Review/Action读写及Windows 11浏览器闭环已完成；Workflow START/只读/历史Schema已完成
涉及模块：workflow、handover、review、evidence、document、capability、trace、project、audit
涉及实体：WFL-01/WFL-02、HND-01/HND-02/HND-03、RVW-01/RVW-02、Evidence、TraceLink
涉及API：后续复用冻结WORKFLOW_CHECKLIST_RECORD/WORKFLOW_TRANSITION；本项不挂载API
涉及权限：ProjectManager记录/推进；Project当前成员、Review、Evidence与Handover Owner各自重验
验收标准：核清两项Checklist的当前事实、依据集合、失败关闭边界、模块端口和后续任务分解
风险：历史APPROVED冒充当前事实、任意Evidence拼接、SUBMITTED/CANCELLED冒充闭环、Workflow直查Handover表、无例外Owner时伪造WAIVED
```

## 当前能力与真实差距

- `HANDOVER_BASELINE`、`HANDOVER_ISSUES` 已存在于不可变六阶段定义和Workflow实例Schema；这只说明“需要检查什么”，不代表检查已执行。
- Handover现在已有真实PROJECT Review Subject Owner。批准终态能形成当前Approved HND-02 Version、CONFIRMED Item、精确Review/Round引用，并在送审与批准时重验固定Document、Capability、Evidence及AI provenance；因此2026-10-02“所有业务Review Owner均缺失”的旧结论对Handover已不再成立。
- HND-03已有OPEN→IN_PROGRESS→SUBMITTED→VERIFIED→CLOSED/CANCELLED完整Owner、固定响应Document/Evidence与Resolution Trace边界。`SUBMITTED`仍不是完成；冻结DM-05明确Gate可消费满足规则的`VERIFIED/CLOSED`。
- Workflow当前只有Checklist追加记录/Transition/Gate Schema和当前记录查询，没有`WORKFLOW_CHECKLIST_RECORD`写服务、Handover资格Owner、ReviewRound当前证明适配或真实Transition应用服务。构造UUID或读取历史APPROVED不能放行。
- Workflow typed refs只能固定`EVIDENCE / REVIEW_ROUND / APPROVED_EXCEPTION`，不会也不应复制Handover正文、Document路径、Capability内容或Action详情。Handover业务资格必须由Handover-owned Port在调用方事务内证明，再转换为最小Workflow观测。

## 两项资格合同

### `HANDOVER_BASELINE`

必须在同一调用方事务内证明：

1. HandoverAnalysis属于目标Project、仍为ACTIVE，`current_approved_version_ref`精确指向被证明版本；Version为APPROVED且内容指纹未漂移。
2. 精确Review/Round属于PROJECT、Subject为`HND-02`、Subject identity/version与当前正式Version一致、Policy为`HANDOVER_ALL_V1`、Round当前为APPROVED，Review subject fingerprint与Handover内容指纹一致。
3. 固定Project DocumentVersion集合当前可访问且物理证明成立；固定CapabilityBaselineVersion仍为当前可用APPROVED版本；固定Capability Item仍AVAILABLE；固定GAP_ANALYSIS Task仍为同项目SUCCEEDED。历史批准不替代这些当前Owner事实。
4. 请求中的Evidence必须来自该正式Version的Item Evidence，或来自下述已合格Action的SUBMISSION/VERIFICATION依据；每条由Evidence Owner当前重验PROJECT归属、ELIGIBLE、版本、指纹和Document定位。任意同项目Evidence不能拼接成PASS。
5. 至少一条当前ELIGIBLE Evidence和一条当前APPROVED ReviewRound观测，满足既有Checklist记录不变量。若项目只有缺失材料且尚无合格Action Evidence，BASELINE保持不能PASS，而不是用Document UUID冒充Evidence。

### `HANDOVER_ISSUES`

先满足同一正式Version、ReviewRound和当前来源证明，再按以下规则失败关闭：

- 因冻结模型没有独立`blocking`字段，本次采用保守且不放宽Gate的确定规则：`source_missing=true`，或`item_type`为`NEED_CONFIRM / CONFLICT / RISK`的Item均视为阻断项；不依据AI置信度、严重度或优先级自行豁免。`MISSING`在`source_missing=true`时包含在内，普通GAP/SCOPE不自动判阻断。
- 每个阻断Item至少存在一条同Project、同当前正式Version、同Item的ANALYSIS_ITEM来源Action达到`VERIFIED`或`CLOSED`；`OPEN / IN_PROGRESS / SUBMITTED`不满足，只有`CANCELLED`也不满足。
- 同一阻断Item若仍存在未取消且未达到`VERIFIED/CLOSED`的相关Action，资格失败关闭；不能用一条已验证重复Action掩盖另一条仍开放的实际事项。
- `VERIFIED`必须重验响应Document、SUBMISSION与VERIFICATION Evidence的当前事实及验证主体/时间；`CLOSED`还须重验Resolution Trace仍ACTIVE、同Project且两端由真实Owner证明。Trace已撤销时不能仅凭历史CLOSED指针推进。
- 当前没有ApprovedException实体/审批Owner，所以本轮不生成风险接受或WAIVED证明。`ACCEPTED_RISK`语义和`APPROVED_EXCEPTION`后续必须由独立正式Owner实现；在此之前相关路径保持失败关闭。

## 适配边界与后续分解

选择Application Port适配，不让Workflow仓储查询`hnd_*`、`rvw_*`或其他Owner内部表：

1. `HND-03-A02`：冻结两项资格的输入/输出和值对象、阻断Item与Action状态规则，使用纯领域测试覆盖正反例；不访问数据库、不写Checklist。
2. `HND-03-A03`：实现Handover-owned当前事实Repository/Owner，在调用方事务内锁正式Version、Review/Round、Item/Action，并调用Document/Capability/Evidence/AI/Trace Owner；输出最小Evidence和ReviewRound观测，不提交事务。
3. `HND-03-A04`：Windows 11/PostgreSQL 18验证真实Owner正反例、并发漂移与零业务写；Server 2025留后续目标环境矩阵，Debian 13按用户指令不实机验证。
4. 随后回到Workflow独立WBS，实现受权Checklist追加命令、Handover策略注册、Review/Evidence重证、Audit/收据和冻结HTTP；再实现Stage Transition。不得把Handover适配器和通用Workflow写服务混成一个WBS。

## 兼容、回滚与验证

本项只做静态前置核查，不改产品代码、Schema/Migration、冻结API、角色、依赖、配置、网络或客户数据，也不需要新的Change Request。后续Port是模块边界内的非破坏性增量；停止注册即可回滚，既有Handover/Workflow历史不改写。

已交叉检查冻结DM-05、API-02、六阶段定义、Workflow当前记录/历史Schema、真实Handover Review Subject、HND-03状态Owner和生产组合。`git diff --check`作为文档质量检查。本结论只证明实施边界已明确，不代表Checklist、Stage Transition、Gate 3或发行通过。
