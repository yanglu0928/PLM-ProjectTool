# A06-P05-P06-P09-P05-A01 PlanVersion需求映射UI编码前检查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A01`
- 结果：`PRECHECK_PASS`
- 变更依据：`CR-PLAN-010`（已先提交并推送）

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3未通过
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A01
输入基线：Gate 2冻结DM-05/API-04 PLAN_VERSION_CREATE；CR-PLAN-010；现有PlanVersion Create Owner/WriteClient；OutlineVersion固定需求Ref；Requirement GET/版本GET只读Client
前置任务：P09-P02不可变草稿创建与固定版本读回已完成；P09-P03 Validate UI、P09-P04 Review送审UI及CR-PLAN-010/浏览器缺口预检已完成并同步
涉及模块：frontend plan PlanVersion Create候选重建、单页多WBS表单与预览；requirement固定版本只读读取；定向/全前端验收
涉及实体：Approved OutlineVersion.requirement_refs固定身份；Requirement当前根对象；RequirementVersion已批准固定正文；PlanVersion WBSItem.requirement_refs
涉及API：只消费已有Requirement GET、RequirementVersion GET与冻结PLAN_VERSION_CREATE POST；无API/Owner/权限/Schema/Migration新增或修改
涉及权限：沿用项目PM/Implementation Member UI门禁；所有读写仍由原SessionClient、CSRF、License、项目授权与冻结Owner校验
验收标准：固定版本每条Outline RequirementRef逐条读取当前Requirement与指定RequirementVersion；校验同Project/根身份/current approved ref/APPROVED状态且无遗漏重复；展示编码、版本标题/陈述和定位链接；允许用户建立1～100个WBS根任务并显式为每条需求分配至少一个任务；任一需求未分配或未受支持则阻止预览/提交；同一需求可分配多个任务；完整冻结字段预览；payload含精确固定Requirement refs且原操作内容/Key未知结果重试不变；读回比较全部WBS任务；来源刷新不兼容则停止；定向测试、全Vitest、typecheck/build
风险：人工映射增加输入工作但避免AI伪造业务拆分；SourceDecision排除/延期输入在本片明确不支持，不得静默忽略；复用已批准版本固定Read不能只读取最新版本；无数据库影响，无客户数据外发
```

## 实施边界

- 仅实现UI与前端只读候选重建，不调整后端覆盖定义或创建校验；保留服务端最终重验。
- 候选加载会对OutlineVersion中引用的每个RequirementRef读取当前根与指定版本；若CURRENT批准引用发生变化或版本并非APPROVED，整体失败关闭。
- WBS每项只接受现有控制代码、唯一编号、名称及至少一项验收标准；依赖/里程碑/排除仍为空，受支持的固定来源字段完整传递。
- 使用A01结果记录；代码修改前本核查先提交并推送。构建/临时输出优先D盘，绝不清理或暂存`.tmp/`。
