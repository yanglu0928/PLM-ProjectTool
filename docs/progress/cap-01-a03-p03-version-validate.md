# CAP-01-A03-P03：Capability Version Validate 报告 Owner

日期：2026-10-05。结论：`CAP_01_A03_P03_VERSION_VALIDATE_PASS`；`CAP-01-A03`完成。下一项：`CAP-01-A04` Review Subject与正式状态Owner前置核查。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A03-P03
输入基线：冻结CAP_VERSION_VALIDATE、Schema0092、CR-CAP-001、DEC-834
前置任务：P01 Baseline与P02完整Draft Version Owner通过
涉及模块：capability只读快照/验证Owner；Document/Evidence Port；Audit回放Source
涉及实体：不修改Version；AuditEvent作为不可变验证结果引用
涉及API：内部Owner；HTTP仍未挂载
涉及权限：当前DeploymentAdmin/CSRF/License、幂等、Audit
验收标准：当前来源PASS/有限失败报告、原Key精确历史回放、新Key重新观察、零状态转换
风险：拿当前状态冒充首次报告；为报告扩张冻结表；把验证PASS冒充Review/APPROVED
```

## 实现与决策

验证Owner锁定不可变Version/Item/Document/Evidence快照，经Document/Evidence Port重新观察当前GLOBAL来源，输出固定`SOURCE_UNAVAILABLE`、`EVIDENCE_UNAVAILABLE` issue code。操作成功与业务验证结论分离：无论valid true/false都形成成功的验证操作Audit，reason_code保存有限结论，Version状态保持DRAFT。

未新增“验证结果表”。幂等收据引用本次不可变AuditEvent；原Key重放从Audit恢复首次trace、观察时间和issue结论，并与不可变Version计数/摘要组合。来源恢复后原Key仍返回首次失败报告，新Key才执行新观察。这样保持冻结五表且不把当前事实伪装成历史结果。

## 验证

- Windows 11 / PostgreSQL 18.6完整P02链上验证：当前来源PASS；Evidence切换CANDIDATE得到`EVIDENCE_UNAVAILABLE`报告；恢复后原Key精确重放失败报告；新Key重新验证PASS；3份Audit/3份收据且Version/正式指针均未变化。标记`CAP_01_A03_P03_VERSION_VALIDATE_PASS`。
- 首轮失效夹具只更新状态但未同步清空eligibility_reason，被既有Evidence检查约束正确拒绝；修正合成夹具形态后从全新库完整重跑，产品约束未放宽。
- 定向6项通过；后端全量2544项通过、3项既有条件跳过、0失败。
- 开发wheel 912项，SHA-256 `9a835fe53819d943e9fe6ce12d6ae13ae84984daccb7aad5e9151d38be6cb9e0`；仅开发检查产物。
- `compileall`与`git diff --check`通过。

## 兼容、回滚与剩余边界

无Migration、公开API、依赖、网络、客户数据或业务状态变化。可停止Validation Owner关闭新报告；既有Audit/收据保留。Validation PASS只证明观察时来源可用和结构完整，不证明内容正确、人工Review或APPROVED。A04 Review/正式指针、HTTP、前端、生产组合仍待；Gate 3及发行阻塞不变。
