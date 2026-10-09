# SOL-03-A04-P01：项目目录使用合格参考的内部证明合同

日期：2026-10-09。结果：`SOL_03_A04_P01_REFERENCE_USE_CONTRACT_PASS`，仅内部合同/校验服务及单测；实际现时证明适配器、目录版本 Owner 仍未完成。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P01。输入：Gate2 DM-05/API-04、CR-SOL-002/016、DEC-1139、0154、SOL-01-A16 资格链。前置：A04 编码前冲突已登记并同步；可先定义受限合同，不依赖未开放目录写。
- 单一问题：ProjectManager/ImplementationMember 引用 GLOBAL 合格 Reference 时，内部 Owner 应得到什么最小现时证明，而不直接调用 GLOBAL 管理员资格命令或泄露来源正文。
- 涉及模块/实体/API/权限：仅 Solution application 的 ReferenceUseQuery、Current snapshot、Source/Confirmation proof 与 Opaque result；无公开 API、DB、权限策略变化。未来 Owner 先授权调用者，再在同一事务内调用证明，项目用户不能直接请求此内部服务。
- 验收：合法 PROJECT/GLOBAL 合同、当前版本/事件、固定来源集合/指纹、GLOBAL 确认身份/时间/撤回失败关闭，端口异常失败关闭；不得把 Mock Port 通过称为真实数据库/来源验收。
- 风险：未接真实 Document/Evidence/Qualification 端口时，合同只能约束未来集成，不证明当前业务可用。

## 实施

新增 `prove_reference_use.py`：同事务当前 Root/Version + 最近合格事件快照、PROJECT 同项目或 GLOBAL 无来源 Project、固定文档/Evidence 集合、源指纹、GLOBAL 人工脱敏确认的最小证明合同；`ReferenceUseProofService` 验证每层身份、Scope、版本、资格、列表一致、摘要、撤回/到期，返回不含正文/定位/管理员会话的 `EligibleReferenceUseProof`。Port 未注入时服务不构造，异常统一失败关闭。所有检查不执行外发。

## 验证、兼容与下一步

Windows 11 Python 3.13 定向 6 项/17 子例通过；后端全量 3413 通过/3 跳过/5216 子例（2 条既有警告）。无 Migration/公开 API/依赖变更，移除该未接线服务可回滚，Reference 历史不受影响。下一独立任务 `SOL-03-A04-P02` 必须完成真实同事务 Reference current/event、Document/Evidence 当前可用性及 GLOBAL 确认的受限适配器，包含隔离 PG/权限/撤回/到期/并发负例；之后才能考虑 A04 Owner/Guard。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-016/DEC-1139 → 本合同 → P02 真实适配器 → OutlineVersion Owner → Gate3。
