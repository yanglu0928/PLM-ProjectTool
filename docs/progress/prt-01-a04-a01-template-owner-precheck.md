# PRT-01-A04-A01：PrototypeTemplate Schema/Owner 前置核查

日期：2026-10-08。结论：`PRT_01_A04_A01_TEMPLATE_PRECHECK_PASS`。下一项：
`PRT-01-A04-A02` GLOBAL/PROJECT Template 与不可变 TemplateVersion Schema0127。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：PRT-01-A04-A01
输入基线：Gate 2冻结PRT-04、M-SCP/V-SCP、API-04六个Template Operation、CR-PRT-001
前置任务：PRT-01-A03 PASS；Schema0126；Prototype Router仍关闭
涉及模块：prototype application/infrastructure、project authorization、deployment admin、document/output Artifact Owner
涉及实体：PrototypeTemplate identity、immutable TemplateVersion、ordered TemplateArtifactRef
涉及API：本项无Router；内部DTO须能无损承接PROJECT/GLOBAL list/create/revise
涉及权限：GLOBAL写仅DeploymentAdmin；PROJECT写仅ProjectManager/ImplementationMember；受权项目成员只读允许的GLOBAL
验收标准：Scope创建后不可变、版本有序且不可改、ArtifactRef固定、同事务Audit/结果/receipt、持久重放重证权限
风险：GLOBAL反写项目事实；任意脚本/执行沙箱；动态latest引用；多态Artifact孤立；版本并发重复
```

## 冻结合同对账与实现决定

- Root 使用 M-SCP：`scope` 只允许 `GLOBAL / PROJECT`，GLOBAL 的 `project_id` 必须为空，PROJECT 必须固定
  有效项目；Scope/ProjectId、创建主体和创建时间不可改。Root 保存名称、状态、当前 TemplateVersion 指针、
  更新时间和乐观锁，不复制版本正文。
- TemplateVersion 使用 V-SCP：每版固定模板 Root、Scope/ProjectId、正整数 `version_no`、32 字节内容指纹、
  被替代版本、创建主体/时间。首版为 1；后续修订必须精确 supersede 当前版本并原子推进 Root 指针。
- 版本正文首版仅保存有界、非可执行的 `layout_contract`、`component_contract` 与规范化适用终端集合；合同是
  结构化 JSON 数据，不接受脚本、命令、绝对路径、外部 URL 抓取或运行入口。AI 只可把它作为 Draft 输入。
- `prt_template_artifact_refs` 是版本拥有的有序固定引用，只允许 `DOCUMENT_VERSION` 或 `OUTPUT_ARTIFACT`。
  A02 物理化引用形状和不可变闭包；A03/A04 分别通过目标 Owner Port 证明目标存在、Scope、项目、状态和固定
  版本。若 OutputArtifact Owner 尚未实现，则该类型失败关闭，不能以裸 UUID 绕过。
- Create 同时创建 Root 与不可变首版，避免无内容模板身份；Revise 追加新版本，不修改旧版本。两类写均有
  不可变首次结果、Audit、持久幂等和提交闭包。List/Get 只返回受权安全元数据与版本合同，不解析制品正文。
- GLOBAL Template 不含客户数据，不得引用 PROJECT Artifact；PROJECT Template 可以引用同项目 Artifact，
  也只能通过目标 Owner 明确允许的 GLOBAL Artifact。模板不会自动生成客户事实、PrototypeVersion 或批准结论。

## 原子子项

1. `A02`：Schema0127，Root/Version/ArtifactRef/写结果及 Owner 关闭、空库与历史库升降验证。
2. `A03`：PROJECT/GLOBAL Create Owner，Artifact proof、首版闭包、权限/Audit/receipt。
3. `A04`：PROJECT/GLOBAL Revise Owner，强 If-Match、当前版并发、supersedes 与不可变历史。
4. `A05`：PROJECT/GLOBAL List/Get 内部读取 Owner、Scope 隔离与安全 DTO。

冻结 HTTP Router 仍留在 `PRT-01-A09` 统一开放；本拆分不增加公开 Operation、依赖、Secret、客户数据外发或
执行沙箱。任一子项失败可停止后续装配，已形成的 TemplateVersion/ArtifactRef/Audit 历史不得删除。
