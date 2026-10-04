# AI-04-A06-P01：Worker / Invocation 执行边界编码前核查

- 日期：2026-10-03
- 结果：`PRECHECK_COMPLETE / CR_REQUIRED / NO_EXTERNAL_CALLS`
- 输入：冻结 ADR-004、DM-04、API-03、Schema0064，AI-04-A05-P05/P06

当前Phase为Phase 2 Platform Core。当前任务只核查最终payload、Invocation、发送前授权/限额/摘要和失败发布边界；不实现Provider调用，不发送客户数据，不修改Schema/API/依赖。

核查确认Schema0064的Invocation/Context/授权快照形态可以继续使用，但现有执行前置只覆盖Task/Job/Prompt引用与当前授权，未提供确定性最终载荷、服务端Token/字节上限、完整InputRef/Context、Invocation原子开始及结果Owner。更关键的是当前AI_TASK Egress Preview摘要由客户端提交，而客户端无法取得完整Prompt并复刻服务端Provider序列化，不能作为实际发送字节的充分证据。

已登记 `CR-AI-015` 并选择服务端确定性 `AIExecutionEnvelope`：Preview、Task创建校验和每次Invocation共用同一构建器；实际摘要/来源/Provider/config/model/region/数据类别/上限不一致即失败关闭。正文只在短生命周期受控内存中存在，不进Job/Outbox/普通日志。旧记录无法证明服务端计划时不可执行，不猜测回填。

Changed：新增CR、决策、进度、状态与版本记录。Files：仅文档。Migration/API/Dependencies：无。Tests：静态核对冻结合同、Schema0064、P05执行前置、Egress Owner和仓库AI模块；未运行新代码测试。Result：P01完成，不把核查当Invocation或Worker PASS。Known Issues：服务端计划、内容Owner、Invocation begin、ModelRouter/Adapter、成功/失败发布均待实现；真实外发仍需逐次明确授权。Next：`AI-04-A06-P02` 内部执行Grant与载荷计划合同。
