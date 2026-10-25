# HND-02-A03-A01：Action 状态 Owner 前置核查

日期：2026-10-05。结论：`HND_02_A03_A01_STATE_PRECHECK_PASS`。下一项：`HND-02-A03-A02` Schema0099生命周期完整性。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-02-A03-A01
输入基线：DM-05、API-04、Schema0098、CR-HND-001/002、DEC-852～854
前置任务：Action Schema与Create Owner已完成
涉及模块：handover、document、evidence、trace、project、audit
涉及实体：HND-03 Root、response/evidence refs、state events、TraceLink
涉及API：核查冻结PATCH/START/SUBMIT/VERIFY/CLOSE/CANCEL，不挂HTTP
涉及权限：PM/IM/assigned owner/受权CustomerManager按冻结Operation分离
验收标准：状态矩阵、owned refs、Trace、强锁、幂等、Audit和回滚边界可逐项实现
风险：SUBMITTED冒充CLOSED、无关Trace冒充解决、通用UPDATE绕过、终态复活、取消抹除历史
```

## 核查结论

- Schema0098正确保持创建后全部生命周期关闭，但不能承载冻结的六个写Operation。
- Root已有提交、验证、关闭投影和强锁；事件已有Actor/reason/time/trace，足以表达前向链与取消，不需要新增Root或公开字段。
- SUBMIT/VERIFY必须通过Document/Evidence Owner固定当前PROJECT事实；CLOSE必须通过Trace Owner验证ACTIVE同项目解决关系，不能只依赖数据库外键。
- Trace不包含HND-03节点是可兼容处理的模型缺口：Action Root以`resolution_trace_ref`绑定解决关系；Analysis来源再匹配固定HND-02 source，人工来源要求显式选择受权下游正式版本并记录关闭reason。无需改变冻结Trace类型。
- 登记`CR-HND-003`，把后续拆为A02 Schema、A03 PATCH、A04 START、A05 SUBMIT、A06 VERIFY、A07 CLOSE/CANCEL；内部Owner完成后再做读取/HTTP/UI，随后返回Handover Review。

## 验证与限制

本项静态交叉核对冻结DM-05/API-04、CR-HND-001/002、Schema0098与现有Document/Evidence/Trace Owner边界；未修改程序、Schema或API，未运行新增程序测试。

真实下游Survey/Requirement版本尚未实现，因此CLOSE机制后续可以用合成合法Trace验证，但不能把合成目标描述为真实项目解决事实；没有合格Trace的Action必须停在VERIFIED。Gate 3继续BLOCKED。
