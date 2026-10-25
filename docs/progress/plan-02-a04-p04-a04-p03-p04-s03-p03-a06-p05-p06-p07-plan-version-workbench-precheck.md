# A06-P05-P06-P07 PlanVersion 固定版本工作页前置核查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P07`
- 结果：`PRECHECK_PASS_WITH_IMMUTABLE_CREATE_RISK`

## 现有页面与读数据

- Plan列表/详情的安全及刷新模式可复用；详情当前只显示Plan身份，`PlanReadClient`将current approved ref严格约束为null，不可推测历史/草稿版本。
- 方案侧已有Outline列表/详情、Outline固定版本分页/详情、Section列表等读取client和相应路由/组件。Outline identity可能给出`current_approved_version_ref`；需读取固定版本确认状态/来源，再构造Plan的固定引用。只显示当前经授权的来源，后端创建时仍需事务内重证。
- 已有PlanVersion单版本详情GET、WBS分页GET、创建、Validate及原子送审写Client；没有PlanVersion collection/history接口。已创建版本ID通过Location/路由保留，不能保证用户离开后可从Plan页重新枚举草稿历史。

## 不可变创建风险与首片边界

- `POST PlanVersion`立即固化不可修改快照；请求须一次包含至少一个Approved Solution固定引用和完整WBS/依赖/里程碑/排除/日历。验证前创建即提交不可编辑事实，不能先造空壳再补录。
- WBS输入字段含层级/编号/类别/负责人/支持角色、日期、状态、准入与验收条件，以及需求/方案/原型/证据映射；Output refs目前会被服务明确拒绝。创建成功后若来源/结构不完整，用户无法原地修订，只能再建版本（且当前接口不提供列表）。
- 本首个UI切片采用严格预览确认：从Plan详情进入“准备新版本”，选一个当前批准Outline根版本，填写至少一个完整WBS根条目与必需验收条件；在发送不可变创建前展示JSON之外的用户友好摘要、明确不可编辑警示与唯一确认动作。无可证明Approved来源、空WBS、缺字段或不支持Output等情况均在客户端前阻止写入；后端仍是最终裁决。
- 先只交付“新版本创建→带version id进入固定详情→详情显示固定快照/WBS”，不在同片混入Validate/Submit UI；后续独立切片在成功读回后增加Validate报告与送审控件。失败/超时必须保留相同key/body；不确定创建不再生成新版本。
- 页面不伪造历史列表；使用直接固定版本路由/已知ID链接，并清晰提示现有限制。不得使用未经证实的审批状态或建议冒充客户确认/正式事实。

## 验收计划 / 边界

- 页面合同覆盖无权项目、缺失批准来源/版本非APPROVED、不可变确认、必填/层级/日期/验收条件、重复提交、跨路由迟到响应和创建不确定状态保留原key。
- 前端全量测试、typecheck/build后，Windows 11 Edge经正式显式Write API和隔离PG执行合成来源→创建→按Location/ID读取的链；若生产合成装配缺条件则记录阻塞，不虚报。
- 本项仅静态核查，无代码、API、Schema、业务数据或数据库变化，未运行新增测试。
- 版本历史enumeration、覆盖完整性/真实批准来源、Validate与SubmitReview UI、Edge及Gate/Pilot/Release仍未完成。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P08`：PlanVersion不可变草稿创建和固定快照读取UI切片编码前核查/实现；不承诺版本历史列表，Validate/Review仍后续。
