# CR-SUR-012：Survey Workflow 资格注册与阶段推进兼容扩展

日期：2026-10-07。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交
`64cdf09`、六阶段 Workflow V1 和现有 Handover 验收行为保留。本 CR 只补齐既定
`SURVEY_ACTUAL_SOURCES`、`SURVEY_CONCLUSION` 运行 Owner 及 `SURVEY → REQUIREMENT` 顺序推进，
不新增阶段、清单项、角色或 `/api/v1` 路径。

## 来源、冲突与客观缺口

六阶段定义已固定 Survey 两个 required Checklist Item；SRV-03/04/05 已拥有 CLOSED Round、
VALIDATED Response、固定 Evidence、不可变 SurveyConclusion、当前来源重证和
`SRV-05 + SURVEY_CONCLUSION_ALL_V1` 正式 Review。但是当前 Workflow 运行链仍有五处 Handover
专用假设：

1. Checklist record 和 qualification preview 只接受两个 `HANDOVER_*` key，并直接依赖
   `HandoverWorkflowCurrentQualificationQuery/HandoverChecklistQualification`；
2. qualification HTTP 投影固定返回 `handover_analysis_version_id`；
3. Stage Transition 只允许 `HANDOVER → SURVEY`，且固定重证 Handover 两项；
4. Windows 组合只装配 Handover Owner；
5. 前端资格、记录与推进客户端只允许 Handover key 和 `target=SURVEY`。

直接把 Survey 硬塞进 Handover DTO、让客户端提交 Response/Conclusion 内部 identity、只检查历史
Checklist PASS，或把模板/AI 建议当实际来源都会破坏模块边界和当前事实重证。完整刷新不恢复内存身份
是已登记体验限制，不在本 CR 通过放宽会话边界解决。

## 选择

### 1. 通用内部资格结果与注册表

- Workflow 增加内部 `CurrentChecklistQualification`：固定 project/stage/item、业务 subject 版本、
  APPROVED ReviewRound、非空 ELIGIBLE Evidence、内容指纹和 Owner coherence key；只输出现有
  `EVIDENCE/REVIEW_ROUND` basis，不新增数据库 ref kind。
- 以不可变 item-key 注册表把 Handover 与 Survey Owner 适配到该结果。未知 key、重复注册、Owner
  返回错 Project/stage/item、空 Evidence、非 APPROVED Review 或不一致 coherence 一律失败关闭。
- 现有 Handover Owner 与既有真实测试保持原行为；通用层只消费 Owner 结果，不直查业务私表。

### 2. Survey 两项的权威语义

- 两项必须绑定同一个当前 APPROVED、未被后继批准版取代的 SurveyConclusion 版本和同一 APPROVED
  ReviewRound；Transition 在同一事务重证两项并比较 coherence key。
- `SURVEY_ACTUAL_SOURCES` 重新证明 Conclusion 所列 CLOSED Round、全部固定 Response 均为当前更正链尾且
  Assignment 为 VALIDATED；PROJECT_RECORD 与答复 Evidence 当前仍 ELIGIBLE、可定位且属于本项目。
  TEMPLATE、MANUAL 说明和 AI Task 均不能单独满足本项；空实际来源不通过。
- `SURVEY_CONCLUSION` 重新证明固定 Conclusion 为 APPROVED，当前来源/冲突/阻断待办校验仍通过，
  Review subject/version/policy 精确为 `SRV-05 / survey_conclusion_id /
  SURVEY_CONCLUSION_ALL_V1`。AI 只作 provenance，不计 Evidence 或确认事实。
- Workflow basis 保存上述 Evidence 与批准 ReviewRound；Conclusion 内容指纹把不可变 Response、Round、
  Evidence/open issue 快照反向绑定到 Review，不扩大 WFL Schema。

### 3. HTTP、前端与兼容

- 原 qualification URL 不变。Handover 成功响应字段保持逐字段完全不变；Survey item 返回独立严格变体，
  以 `survey_conclusion_id + review_round_ref + evidence_refs` 表示，不向旧 Handover 响应添加字段。
- 冻结 Checklist record 请求继续只提交服务器预览得到的 `evidence_refs`；Response、Conclusion 和
  Review identity 均由服务器重新解析，客户端不能指定或猜测。
- 前端按当前 stage 选择受支持 item 和顺序 target；Survey 只允许 `SURVEY → REQUIREMENT`。未知阶段、
  stale ETag、跨阶段 item、网络结果不确定均沿用现有失败关闭与原幂等 Key 恢复规则。

## 实施拆分

1. `SUR-06-A01`：本 CR、差距矩阵、兼容/迁移/回滚和验证计划。
2. `SUR-06-A02`：通用内部 qualification contract/registry 与 Handover 兼容 adapter。
3. `SUR-06-A03`：Survey 两项 current-fact policy、Repository/Owner 与单元负例。
4. `SUR-06-A04`：Checklist preview/record、Stage Transition 和 Windows 组合接入 Survey registry；
   保持原 Handover HTTP 响应不变。
5. `SUR-06-A05`：Windows 11/PostgreSQL 18.6 真实 Checklist、同事务重证、并发/漂移和
   `SURVEY → REQUIREMENT` 验证。
6. `SUR-06-A06`：前端严格双阶段资格/记录/推进支持及全量回归。
7. `SUR-06-A07`：真实 Edge 完成合成项目 `HANDOVER → SURVEY → REQUIREMENT`、Evidence 定位、审计、
   幂等恢复和隔离清理；只证明前两阶段闭环，不冒充六阶段完整项目或 Gate 3 通过。

## 风险、迁移与回滚

- 无 Schema/Migration：现有 WFL basis 已支持 ELIGIBLE Evidence 与 APPROVED ReviewRound，Survey
  业务版本通过 Review 指纹和 Owner 当前重证绑定。若实现证明该集合不足，必须另开 Schema CR，不能
  把业务 UUID 塞入错误 ref kind。
- 风险为通用化回归 Handover；每一步保留现有 Handover 单元、HTTP、PG 和浏览器证据，注册表采用显式
  allowlist，不做动态 import 或插件发现。
- 应用回滚可移除 Survey 注册和前端分支，恢复仅 Handover；已写 Checklist/Transition 历史保留，
  不重写、不降级。A07 fixture 仅用隔离合成数据并清理。
- 本 CR 无依赖、Secret、客户数据外发或 License 变化；不证明 Windows Server 2025、Debian 13、
  20 并发、UAT、发行或 Gate 3。Debian 13 实机继续按用户指令跳过但保留兼容目标。

## 验证计划

- 静态：Catalog 两项、业务 Owner、Review policy、当前五处 Handover 硬编码及注册表边界对账。
- 单元/合同：未知/重复注册、错 stage/item/project、空 Evidence、非批准 Review、stale/superseded
  Conclusion、模板/AI-only、未验证 Response、来源/待办漂移和 Handover 响应逐字段兼容。
- PostgreSQL 18.6：同事务锁序、两项同 Conclusion/Review coherence、Checklist append、并发版本、
  Audit/receipt 回滚、Transition gate snapshot 与 Handover 旧链回归。
- 浏览器：生产 Vue/FastAPI/PG 经 Survey 资格预览、两项 PASS、二次确认推进 REQUIREMENT，截图、网络
  状态、SQL历史和清理均通过。

## 实施记录

- 2026-10-07 / `SUR-06-A02`：新增业务中立的current qualification query/result、Evidence/Review
  observation、显式只读item-key registry及Handover compatibility adapter；重复/未知注册、错身份、
  空Evidence、非批准Review与Owner异常全部失败关闭。未接生产service/HTTP，原Handover运行行为不变。
  新增6、既有Handover/Workflow定向37、后端2948/3及wheel1107项通过，进入A03 Survey Owner。
