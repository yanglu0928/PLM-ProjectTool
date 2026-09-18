# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13-R3：R6 六项问题与引用人工复核|
|Current Status|AWAITING_R6_HUMAN_CONFIRMATION|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|方案 A 已获批准并生成 R6，仅复核 6 条低区分度问题与引用；工作簿仍为“未确认”，R6 Golden Dataset 尚未生成，P03-A12/A13 重跑不得开始|
|Pending User Decisions|在 R6 工作簿 B5 选择“确认全部AI建议”，填写确认人和日期；如个别建议不适用，仅维护对应黄色列|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 107/107 单元测试 PASS；R6 工作簿三表渲染/回读、公式错误扫描、未确认严格导入均 PASS；当前 6 条 PENDING、0 个校验问题，114 条及全部 R5 标签锁定不变|
|Next WBS|等待 R6 人工批量确认；确认后严格导入 R6、重跑 P03-A11~A13，并按结果继续分类 Prompt v2 或升级异常|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 47%，剩余 53%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户已批准方案 A。R6 将复核范围锁定为 GD-0016、0018、0020、0023、0075、0091，只建议修订问题与引用，不改变分类；其余 114 条逐对象保留。工作簿支持一次批量确认、单条例外及本地证据跳转，未确认前导入器不生成 R6 数据集。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
