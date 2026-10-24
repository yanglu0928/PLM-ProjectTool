# REQ-01-A10-A08：Requirement Windows 显式组合

日期：2026-10-08。结论：`REQ_01_A10_A08_WINDOWS_COMPOSITION_PASS`。下一项：
`REQ-01-A11-A01` 前端来源定位、人工输入提示与 Edge 闭环前置核查。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A08
输入基线：冻结API-01/API-04、REQ-01/REQ-03/REQ-04、CR-REQ-001
前置任务：A10-A02～A07全部PASS
涉及模块：Windows production composition、Requirement四类Router、统一PROJECT Review
涉及实体：无新增；复用Requirement、Version、Relation、Review、Receipt、Audit
涉及API：只读模式七个GET；写模式全部22个Requirement Operation
涉及权限：沿用各Owner的Project成员/经理/实施成员/Reviewer策略
验收标准：四类独立密钥、失败关闭、两模式精确路由、REQ-03统一终态决策、真实PG组合证明
风险：只读模式误暴露写路由；资源族共享cursor；送审后统一Review找不到Subject Owner
```

## 结果

- 新增 `windows_requirement` 生产组合根，分别解析Package、Requirement、Version、Relation四个
  32字节cursor密钥；任一缺失、长度错误或组合异常均以固定启动错误失败关闭，不暴露原始原因。
- 只读模式从真实四类Router精确保留七个GET，不发布POST/PATCH；写模式发布6+7+4+1+4共22个
  冻结Operation。所有Router仍经显式注入进入生产应用。
- Windows生产入口在platform/read和platform/write模式均装配Requirement；统一PROJECT Review
  Registry新增`REQ-03` Owner，因此业务原子送审后的approve/return/withdraw可进入同一决策链。
- 定向组合/Review/生产入口38项与6个子测试通过；完整后端3066项通过、3项既有条件跳过。
- `validation/req-01-a10-a08-windows-composition/verify.py` 在Windows 11/PostgreSQL 18.6空库升至
  head并通过Alembic drift，使用实际生产组合执行Package六个HTTP、权限/License/Audit/回放；同时
  核验四类密钥解析、七读/十五写共22个路由及统一Review四命令装配。A03～A07既有真实PG证据分别
  覆盖其余16个Requirement Operation；本项不把路由盘点冒充每个操作的重复业务执行。
- 开发wheel 1165项，包含新生产组合模块，SHA-256
  `5d17adad7bb12204aa92bbdad874ea54b99b61ac239d1715b54a1242e039f426`。
- 无Schema/Migration、依赖、客户数据或外发变化。部署前必须为目标Windows服务账户供给四个新cursor
  密钥；缺密钥时平台模式按设计拒绝启动。停止Requirement Router注入可回滚流量，历史数据保留。
