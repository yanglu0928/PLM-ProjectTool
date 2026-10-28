# PLT-PKG-01-A09-P51-A27：云端父包 PlanVersion Edge/HTTPS/PG 闭环编码前检查

- 日期：2026-10-28
- WBS：`PLT-PKG-01-A09-P51-A27`
- 前置：P51-A26 PASS_LIMITED；A17 包内 PlanVersion Edge 验收仍未完成，旧阻塞为本机 C 盘空间与合成 Approved Section Owner fixture 未复验。
- 关联：`CR-EXEC-002`、`CR-EXEC-003`、`CR-EXEC-005`、`CR-PLAN-011/012`；本项按 CR-EXEC-003/005 在 hosted Windows runner 重建并执行，不使用或上传本机候选包。
- 状态：`PRECHECK_PASS_WITH_CLOUD_HARNESS_ADAPTATION`

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3 未通过
当前WBS：PLT-PKG-01-A09-P51-A27
输入基线：冻结 DM-05/API-04 PlanVersion Create/GET/Validate/SubmitReview；CR-PLAN-010～012；P09-P01～P09-P05-A02 已验 UI/Owner/PG/HTTP/Edge 证据；P51-A17 合成 PlanVersion packaged harness；CR-EXEC-005 官方来源重建父包；P51-A26 PASS_LIMITED staging
前置任务：PR #56 当前 head 已核对；A26 逐项完整性/安全暂存通过；云端父包 assembly、A17 fixture 与当前业务 package smoke 可在 workflow 同提交执行
涉及模块：仅 GitHub hosted Windows 2025 workflow、一次性验证 Harness、A17 Edge runner、结果文档及 STATUS/CHANGELOG；不改产品业务模块
涉及实体：合成 Project/PM/客户评审人、Approved Outline/Section/Requirement 固定版本、PlanVersion/WBS、ValidationReport、Review/Round/Audit/Idempotency Receipt
涉及API：现有包内 Login、Outline/Requirement 固定读取、PlanVersion Create/GET/Validate/SubmitReview、Review GET；不新增或改变产品 API
涉及权限：真实包内 Session/CSRF/Project角色路径；License、发行信任、来源和评审身份均明确为合成测试 fixture，不构成客户确认
验收标准：同一 workflow commit 构建并核验父包；Windows hosted runner 在非 C RUNNER_TEMP 及其子目录运行；清洁解包和包摘要校验；Edge 通过真实包 HTTPS API 完成固定来源读取→显式 WBS 映射→创建→固定 ID 读回→Validate→原子送审→合成评审人只读；PG 独立核对版本映射/Validation/Audit/Receipt/Review/Round 且 Decision=0；所有数据库、Edge profile、日志、截图、临时文件均位于 D 盘 runner 临时目录并只清理本轮拥有的资源；完整后端/前端及工作流验收通过，最终检查 Secret 与产物摘要；限制明确保持 PASS_LIMITED
风险：Runner 资源或官方来源不可用；旧 fixture owner/CSRF 错误；现有 harness/node/browser 可能写系统 Temp。任何无法证明位于非 C 盘的写入点须先关闭或改为显式 RUNNER_TEMP；不得访问用户本机、用户数据、正式密钥或真实客户内容。
```

## 单一任务范围

只恢复 A17 的包内 PlanVersion Edge/HTTPS/PostgreSQL 合成业务闭环验收，并将 Harness 迁移到 hosted runner 唯一临时路径。产品 API/Schema/ORM/Migration/依赖及许可行为不变；不安装至真实产品根、不做真实客户批准、不把合成信任当正式信任。若 runner 上环境/官方来源不可用，记录可复现诊断并转向不依赖该条件的 WBS。

## 偏差与恢复

- 偏差：既有 A17 harness 固定写入 `D:\\PLMToolTemp`，并由本机执行环境触发；新策略要求任何执行仅在托管云端沙箱。
- 选择：改为接受 workflow 提供的非 C 盘 `RUNNER_TEMP` 子目录，并在父子进程及浏览器 profile 验证路径归属；所有资源通过本轮唯一 run ID 隔离。
- 影响：仅验证工具/Workflow；不改变产品功能或冻结基线。托管 Windows Server 2025 结果不等同 Windows 11 实机通过。
- 回滚：丢弃本 WBS 新增 Harness/workflow 调用与文档，不改产品实现/Schema；历史 A17 失败与 P51-A26 候选证据保留。
- 验证：先静态审查所有临时路径和资源清理，再由 hosted Windows workflow 执行；不调用本机测试，不上传用户本机归档、客户资料、日志、凭据或密钥。

## 状态边界

完成时至多记录 `PASS_LIMITED`。Pilot 仍需真实正式 License 信任、安全服务账户/TLS、离线安装升级及其他范围验收；Gate 3、Windows 11 实机与正式多平台 Release 均不由本项关闭。
