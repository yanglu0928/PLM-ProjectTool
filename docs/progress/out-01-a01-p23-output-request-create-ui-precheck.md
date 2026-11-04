# OUT-01-A01-P23：批准需求版本的 Output DOCX 请求入口编码前检查

- 日期：2026-11-05
- 结果：PASS_WITH_LIMITATION
- Change Request：CR-OUT-019
- 前置：P12 Create HTTP 与 P19 Windows write组合已按CR-OUT-009/015限界通过；Requirement fixed-version read UI已有 APPROVED/current_approved_version_ref；P22列表UI代码已提交。
- 执行约束：不在开发者本机/C盘运行项目程序或测试；仅GitHub hosted runner D盘临时目录/云沙箱。

## 单一问题

用户是否能在项目需求的已批准固定版本详情中，主动发起一个受服务端鉴权的内置DOCX请求，并清楚区分“请求被接受”与“文件已生成”。

## 编码前检查证据

- 冻结 API-03 已有 POST /api/v1/projects/{project_id}/output-requests，body为固定5字段：output_type、template_version_ref、source_version_refs、output_policy_ref、plugin_operation；P12 Create HTTP由P19组合提供，使用Session/CSRF/Idempotency与Owner。
- 当前前端 SessionClient 的固定POST路径白名单没有OutputRequest Create；须增加单一精确路径和窄方法，不能用任意URL通用POST绕过授权。
- RequirementReadClient已暴露版本状态、requirement_version_id和当前批准版本引用；固定版本详情已有APPROVED标记。按钮仅在当前批准版本自身状态APPROVED且它与requirement.current_approved_version_ref一致时出现。
- 现有builtin registry仅包含DOCX/RequirementVersion；模板、Policy和operation固定为CR-OUT-019列出的产品常量。用户提交的source ref必须是选定的当前批准版本；不允许通过表单自填内部UUID/插件操作。
- Create角色按P19/冻结合同限定PM与Implementation Member；UI角色是展示提示，服务端Create Access/License/CSRF/Publisher trust为最终边界。
- P19编码前证据：包内publisher key清单为空；因此真实Create会失败关闭，不得产Job或伪造成功。该现实限制不阻止UI与合成客户端测试，但必须明显提示仅“已接受请求”才可显示，不把模拟成功写入业务事实。
- 不需要Schema/API迁移。代码集中于SessionClient固定路由、Output Create client与Requirement详情入口；无AI、插件运行、文件输出、客户数据外发。

## 验收与风险

定向client/view测试覆盖payload固定、CSRF/Idempotency通道、角色/批准状态门控、timeout/不确定结果保留原key，以及安全错误提示；全量Vue测试/typecheck/build及原有Hosted矩阵。若trusted publisher未配置，Hosted合成状态仅验证拒绝安全路径，不能证明真实生产请求可入队或插件可生成文件。Pilot/Gate/Release状态不变。

## 结论

PASS_WITH_LIMITATION：可实施前端请求入口，但它只能创建受Owner控制的请求；真实publisher信任未满足时保持失败关闭。代码前必须保留本限制，不通过固定客户端key或测试信任源伪装产品可用。