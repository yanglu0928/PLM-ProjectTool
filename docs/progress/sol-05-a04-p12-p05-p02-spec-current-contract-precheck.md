# SOL-05-A04-P12-P05-P02：Section Spec 现时证明合同编码前检查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`INTERNAL_CONTRACT_PASS`。

|检查项|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `SOL-05-A04-P12-P05-P02`；为既有六维VALIDATE增加可注入只读Spec现时证明合同|
|输入基线|Gate 2六维合同、CR-SOL-022/023、P05-P01边界、0182同事务作者依据Owner；冻结路径/响应状态值不改|
|前置任务|Section固定Spec已可受控写入和反读；CREATE资格已有真实Windows/PG证据，VALIDATE仍恒UNAVAILABLE|
|模块/实体|Solution SectionVersionCurrentValidator、SectionVersionHistoryView、固定SpecRef与现时证明端口；无Schema/迁移|
|API/权限|原VALIDATE的Session/项目授权/License/幂等/Audit沿用；无新HTTP路由、角色或权限|
|验收标准|未声明永不PASS；有规范理由且零引用的NONE_REQUIRED可给送审准备PASS；FIXED_REFS仅在逐条规范依据、完整精确现时资格证明后PASS；缺端口/错源/异常/部分集合/缺依据失败关闭；旧Key回放首次观察，正文/Trace失败仍阻止ready_for_review|
|风险|只验作者文字却未重证当前批准Spec，或把创建时资格/客户Review替代现时证明；本片仅注入可信端口合同，P05-P03才安装Windows真实PG适配器|

本合同不宣称自动语义正确、正式客户批准或已完成P05-P03组合验收。

## 实施与独立验收

- 复用CREATE与VALIDATE共同的规范化有界作者依据语法，旧请求/指纹/首次201无变化。
- `SectionVersionCurrentValidator`新增可选`CurrentSpecPort`，只接收同事务、与目标版本固定引用逐项一致的类型化现时证明；缺适配器、缺/非法依据、少项/错项、空Review/来源/共同需求、端口异常均`UNAVAILABLE`。`NONE_REQUIRED`在DRAFT、有效理由且零引用时给送审准备PASS，`UNDECLARED`永不PASS。
- 旧幂等Key回放首次六维事实；新Key重采样。Spec PASS不覆盖正文/Trace失败，也不创建Review或改变Section状态。
- 定向测试35通过/40子例；完整后端3918通过、3跳过、6070子例。没有Schema变化；本片尚未安装真实Windows/PG SpecPort，FIXED_REFS在当前组合仍为UNAVAILABLE，转P05-P03。
