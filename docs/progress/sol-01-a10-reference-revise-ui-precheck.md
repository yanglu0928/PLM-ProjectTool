# SOL-01-A10：Reference Revise 前端施工前置核查

日期：2026-10-09。结果：`SOL_01_A10_REFERENCE_REVISE_UI_PRECHECK_PASS`；仅前置核查与分片计划，前端修订功能未实现/未验收。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A10；冻结 API-04、CR-SOL-013、A07～A09 真实 Owner/HTTP/Windows 写组合满足前置。
- 模块/实体/API/权限：前端 Auth 写桥、Solution PROJECT/GLOBAL Reference 当前详情和候选选择；服务端 PROJECT PM/实施成员、GLOBAL DeploymentAdmin 保持不变。无 Schema/Migration/依赖/冻结 API 变化。
- 验收：明确当前 ETag 来源、来源选择/脱敏确认、幂等不确定结果和历史 201 呈现边界；列出独立前端/浏览器 WBS，不把静态核查标记为 UI PASS。
- 风险：旧 201 的 ETag 不是后续根当前 ETag；重放后若直接显示“当前版本”会误导。修订新来源仍需服务端重新证明，GLOBAL 更需新指纹对应人工脱敏确认。不得把只读详情或自由文本 UUID 表单当合格来源选择。

## 对账与选择

PROJECT/GLOBAL 详情 GET 已提供当前版本 ID、`etag`、固定文档与证据 ID、来源分类及适用性；页面已有打开固定文档/证据原文的可追溯入口。现有前端 Auth 写桥覆盖 GLOBAL Reference Create、Section Create，但没有 Reference Revise；现有 Global Source Picker/脱敏确认可复用其候选和确认语义，PROJECT 尚无对应 Reference 创建/来源选择页。不能只加一个按钮并把当前 ID 原样重发：用户无法选择要修订的内容，GLOBAL 变更来源也缺新确认。

选择分片实施：A11 先补单次受保护写传输和严格 201/错误客户端；A12 建 PROJECT 来源候选/修订页并显式展示当前版本、待选来源及当前性警告；A13 将 GLOBAL 已有来源选择/脱敏确认流程接入修订，并区分新建与修订；A14 Win11 Edge/隔离 PG 验证角色、来源变更、历史结果恢复及跳转后当前 GET。页面只从新读取的 GET 取得当前 ETag；同键重试保留原 If-Match/Key，成功后必须重新 GET，不以旧 201 判定当前。若候选接口不支持合格选择，应在相应 WBS 先补受控候选，不用裸 UUID 自由填写绕过。

## 兼容与后续

本项仅文档/排期，无新测试，不改变既有程序。TraceLink：Gate2 API-04 → CR-SOL-013 → A07～A09 → 本 A10 → A11～A14 → Eligibility。正式目标账户、20 并发、Server2025、Gate3/UAT/可用程序包仍未验；Debian13 实机按用户指令暂跳过。
